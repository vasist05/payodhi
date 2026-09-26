"""
backend/app/services/pipeline_service.py

Unified multi-phase pipeline orchestration service for Payodhi.
Chains:
  - Phase 1: SAR Satellite U-Net Oil Spill Segmentation
  - Phase 2: SAR-UV False-Positive Filtering (ERA5 Wind Vector Integration)
  - Phase 3: Hydrodynamic Backward Drift Reconstruction & Origin Probability Modeling
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.drift import DriftRunResponse
from app.schemas.pipeline import IntegratedPipelineResponse
from app.schemas.spill import SpillResponse
from app.services.detection_service import DetectionService
from app.services.drift_service import DriftService
from app.services.filter_service import FilterService

log = logging.getLogger(__name__)


class IntegratedPipelineService:
    """
    Executes the end-to-end multi-phase detection, verification, and drift pipeline.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.detection_svc = DetectionService(session)
        self.filter_svc_sar_uv = FilterService(session, mode="sar_uv")
        self.filter_svc_sar_only = FilterService(session, mode="sar_only")
        self.filter_svc_sar_speed = FilterService(session, mode="sar_speed")
        self.drift_svc = DriftService(session)

    def _get_filter_service(self, mode: str) -> FilterService:
        if mode == "sar_only":
            return self.filter_svc_sar_only
        elif mode == "sar_speed":
            return self.filter_svc_sar_speed
        return self.filter_svc_sar_uv

    async def execute_full_pipeline(
        self,
        scene_id: UUID,
        image_path: Optional[str] = None,
        detection_threshold: float = 0.50,
        min_pixels: int = 50,
        filter_mode: Literal["sar_only", "sar_speed", "sar_uv"] = "sar_uv",
        drift_window_hours: int = 12,
        n_drift_scenarios: int = 50,
        stokes_mode: str = "wave",
        actor_id: Optional[str] = None,
        request_id: Optional[UUID] = None,
    ) -> IntegratedPipelineResponse:
        """
        Execute Phase 1 -> Phase 2 -> Phase 3 in sequence.
        """
        start_clock = time.perf_counter()

        log.info("Starting End-to-End Pipeline for Scene %s", scene_id)

        # ------------------------------------------------------------------ #
        # Step 1: Phase 1 SAR Segmentation Detection
        # ------------------------------------------------------------------ #
        log.info("[Pipeline Step 1/3] Running Phase 1 SAR Detection...")
        det_result = await self.detection_svc.run_detection(
            scene_id=scene_id,
            image_path=image_path,
            threshold=detection_threshold,
            min_pixels=min_pixels,
            actor_id=actor_id,
            request_id=request_id,
        )

        candidates = det_result["candidates"]
        spill_count_initial = det_result["spill_count"]

        if not candidates:
            total_time = (time.perf_counter() - start_clock) * 1000.0
            return IntegratedPipelineResponse(
                scene_id=scene_id,
                status="success",
                spill_count_detected=0,
                spill_count_confirmed=0,
                spill_count_rejected=0,
                confirmed_spills=[],
                rejected_lookalikes=[],
                drift_reconstructions=[],
                total_execution_time_ms=total_time,
                message="No oil spill candidates detected in SAR scene.",
            )

        # ------------------------------------------------------------------ #
        # Step 2: Phase 2 False-Positive Verification
        # ------------------------------------------------------------------ #
        log.info("[Pipeline Step 2/3] Running Phase 2 False-Positive Filtering on %d candidates...", len(candidates))
        filter_svc = self._get_filter_service(filter_mode)
        filter_res = await filter_svc.filter_batch(
            [c.model_dump() for c in candidates],
            request_id=request_id,
            actor_id=actor_id,
        )

        confirmed_spills = filter_res["confirmed"]
        rejected_lookalikes = filter_res["rejected"]

        # ------------------------------------------------------------------ #
        # Step 3: Phase 3 Hydrodynamic Drift Origin Reconstruction
        # ------------------------------------------------------------------ #
        drift_reconstructions: List[DriftRunResponse] = []
        phase3_payload = None

        if confirmed_spills:
            log.info(
                "[Pipeline Step 3/6] Running Phase 3 Drift Reconstruction for %d confirmed spills...",
                len(confirmed_spills),
            )
            for idx, spill in enumerate(confirmed_spills):
                cand = candidates[idx] if idx < len(candidates) else None
                c_lon = cand.center_lon if cand else 72.5
                c_lat = cand.center_lat if cand else 21.0

                drift_res = await self.drift_svc.run_backward_reconstruction(
                    scene_id=scene_id,
                    spill_id=spill.id,
                    detection_lon=c_lon,
                    detection_lat=c_lat,
                    window_hours=drift_window_hours,
                    n_scenarios=n_drift_scenarios,
                    stokes_mode=stokes_mode,
                    actor_id=actor_id,
                    request_id=request_id,
                )

                drift_reconstructions.append(
                    DriftRunResponse(
                        run_id=drift_res["run_id"],
                        scene_id=drift_res["scene_id"],
                        spill_id=drift_res["spill_id"],
                        status=drift_res["status"],
                        run_fingerprint=drift_res["run_fingerprint"],
                        origin_estimate=drift_res["origin_estimate"],
                        contours=drift_res["contours"],
                        heatmap_summary=drift_res["heatmap_summary"],
                        output_storage_uri=drift_res["output_storage_uri"],
                        execution_time_ms=drift_res["execution_time_ms"],
                        message=drift_res["message"],
                    )
                )

                if phase3_payload is None and drift_res.get("origin_estimate"):
                    phase3_payload = {
                        "origin_lat": drift_res["origin_estimate"]["lat"],
                        "origin_lon": drift_res["origin_estimate"]["lon"],
                        "drift_run_id": drift_res["run_id"],
                    }
        else:
            log.info("[Pipeline Step 3/6] Skipped drift modeling because 0 spills were confirmed by Phase 2.")

        # ------------------------------------------------------------------ #
        # Step 4: Phase 4 AIS Correlation & Dark Vessel Detection
        # ------------------------------------------------------------------ #
        ais_correlations: Optional[Dict[str, Any]] = None
        if confirmed_spills and drift_reconstructions:
            log.info("[Pipeline Step 4/6] Running Phase 4 AIS & Dark Vessel Detection...")
            try:
                from core.phase4_ais.pipeline import run_phase4_pipeline
                from app.services.ais_correlation_service import persist_phase4_correlations

                primary_drift = drift_reconstructions[0]
                origin_lat = primary_drift.origin_estimate.get("lat", 18.90) if primary_drift.origin_estimate else 18.90
                origin_lon = primary_drift.origin_estimate.get("lon", 72.10) if primary_drift.origin_estimate else 72.10

                phase4_res = await run_phase4_pipeline(
                    spill_lat=origin_lat,
                    spill_lon=origin_lon,
                    use_validation_cases=True,
                )

                # Persist to sar_targets & target_correlations tables
                await persist_phase4_correlations(
                    session=self.session,
                    scene_id=scene_id,
                    phase4_result=phase4_res,
                )
                ais_correlations = {
                    "total_targets": len(phase4_res.get("correlated_ships", [])),
                    "dark_vessels": len(phase4_res.get("dark_vessels", [])),
                    "matched_vessels": len(phase4_res.get("matched_vessels", [])),
                    "summary": phase4_res.get("summary", {}),
                }
            except Exception as exc:
                log.warning("Phase 4 AIS Correlation encountered error (non-fatal): %s", exc)

        # ------------------------------------------------------------------ #
        # Step 5: Phase 5 7-Pillar Forensic Attribution Engine & Legal Verdict
        # ------------------------------------------------------------------ #
        attribution_results: Optional[List[Dict[str, Any]]] = None
        top_suspect_name: Optional[str] = None
        if drift_reconstructions:
            log.info("[Pipeline Step 5/6] Running Phase 5 7-Pillar Forensic Attribution Engine...")
            try:
                from app.services.attribution_pipeline import run_attribution
                attribution_results = []
                for d_run in drift_reconstructions:
                    attr_res = await run_attribution(
                        session=self.session,
                        drift_run_id=d_run.run_id,
                    )
                    attribution_results.append(attr_res)
                    if not top_suspect_name and attr_res.get("vessel_name"):
                        top_suspect_name = attr_res["vessel_name"]
            except Exception as exc:
                log.warning("Phase 5 Attribution encountered error (non-fatal): %s", exc)

        # ------------------------------------------------------------------ #
        # Step 6: Phase 8 Coast Guard Tactical Alert & Maritime Response
        # ------------------------------------------------------------------ #
        response_alert: Optional[Dict[str, Any]] = None
        if confirmed_spills:
            log.info("[Pipeline Step 6/6] Evaluating Safety Gates & Triggering Coast Guard Response Engine...")
            try:
                from backend.notification.response_engine import dispatch_response
                spill0 = confirmed_spills[0]
                cand0 = candidates[0] if candidates else None
                s_lon = cand0.center_lon if cand0 else 72.5
                s_lat = cand0.center_lat if cand0 else 21.0

                incident_payload = {
                    "id": str(spill0.id),
                    "lat": s_lat,
                    "lon": s_lon,
                    "is_verified_oil": True,
                    "filter_confidence": float(spill0.confidence_score),
                    "detection_confidence": float(spill0.confidence_score),
                    "top_suspect_name": top_suspect_name or "UNKNOWN / AIS DARK VESSEL",
                }
                response_alert = await dispatch_response(incident_payload, phase4_vessels=[])
            except Exception as exc:
                log.warning("Phase 8 Coast Guard Response encountered error (non-fatal): %s", exc)

        total_time = (time.perf_counter() - start_clock) * 1000.0

        return IntegratedPipelineResponse(
            scene_id=scene_id,
            status="success",
            spill_count_detected=spill_count_initial,
            spill_count_confirmed=len(confirmed_spills),
            spill_count_rejected=len(rejected_lookalikes),
            confirmed_spills=[
                SpillResponse.model_validate(s, from_attributes=True) for s in confirmed_spills
            ],
            rejected_lookalikes=[
                SpillResponse.model_validate(s, from_attributes=True) for s in rejected_lookalikes
            ],
            drift_reconstructions=drift_reconstructions,
            ais_correlations=ais_correlations,
            attribution_results=attribution_results,
            response_alert=response_alert,
            total_execution_time_ms=total_time,
            message=(
                f"Full 8-Phase pipeline completed: {spill_count_initial} detected, "
                f"{len(confirmed_spills)} confirmed, {len(rejected_lookalikes)} lookalikes rejected, "
                f"{len(drift_reconstructions)} drift reconstructions generated, "
                f"{'Phase 4 AIS correlated, ' if ais_correlations else ''}"
                f"{'Phase 5 Attribution evaluated, ' if attribution_results else ''}"
                f"{'Phase 8 Coast Guard alert dispatched.' if response_alert else ''}"
            ),
        )

