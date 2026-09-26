"""
backend/app/services/drift_service.py

Phase 3 Hydrodynamic Drift Model Service Layer.
Orchestrates backward trajectory origin reconstruction (Monte Carlo ensemble),
computes 2D probability heatmaps and cumulative confidence contours, and
evaluates forward vessel release attribution.

Persists to PostgreSQL/PostGIS (drift_runs Table 5) and appends to audit_log (Table 8).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import DriftStatusEnum
from app.repositories.audit_repo import AuditRepository
from app.repositories.drift_repo import DriftRepository
from app.repositories.scene_repo import SceneRepository
from app.repositories.spill_repo import SpillRepository
from app.schemas.drift import (
    CandidateScoreResponse,
    ConfidenceContour,
    DriftRunResponse,
    ForwardAttributionCandidateRequest,
    ForwardAttributionResponse,
    HeatmapSummary,
    OriginEstimate,
)
from core.phase3_drift.drift_model.aggregate import (
    build_heatmap,
    confidence_contours,
    contour_to_polygon,
    peak_location,
)
from core.phase3_drift.drift_model.forcing import (
    load_forcing_safe,
    make_synthetic_current,
    make_synthetic_wind,
)
from core.phase3_drift.drift_model.orchestrate import full_backward_pipeline
from core.phase3_drift.drift_model.sampler import sample_scenarios
from core.phase3_drift.forward_attribution.rank import classify_attribution, rank_candidates
from core.phase3_drift.forward_attribution.scorer import score_vessel

log = logging.getLogger(__name__)

SIMULATION_VERSION = "opendrift-openoil-v1.0"


def _compute_fingerprint(
    scene_id: UUID,
    spill_id: Optional[UUID],
    lon: float,
    lat: float,
    det_time: datetime,
    window_hours: int,
    n_scenarios: int,
    stokes: str,
) -> str:
    """Deterministic 64-char SHA256 hex string for drift run deduplication."""
    payload = f"{scene_id}:{spill_id}:{lon:.5f}:{lat:.5f}:{det_time.isoformat()}:{window_hours}:{n_scenarios}:{stokes}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DriftService:
    """
    Coordinates hydrodynamic drift reconstruction, probability estimation,
    and database persistence.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.drift_repo = DriftRepository(session)
        self.scenes = SceneRepository(session)
        self.spills = SpillRepository(session)
        self.audit = AuditRepository(session)

    async def run_backward_reconstruction(
        self,
        scene_id: UUID,
        spill_id: Optional[UUID] = None,
        detection_lon: Optional[float] = None,
        detection_lat: Optional[float] = None,
        detection_time: Optional[datetime] = None,
        window_hours: int = 12,
        n_scenarios: int = 50,
        stokes_mode: str = "wave",
        force_rerun: bool = False,
        actor_id: Optional[str] = None,
        request_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Execute Phase 3 backward ensemble drift simulation for an oil spill,
        generate probability heatmap, contours, and persist drift_runs row.
        """
        start_clock = time.perf_counter()

        scene = await self.scenes.get_by_id(scene_id)
        if scene is None:
            raise ValueError(f"Scene with ID '{scene_id}' not found.")

        # Resolve detection centroid & time
        if detection_lon is None or detection_lat is None or detection_time is None:
            if spill_id is not None:
                spill = await self.spills.get_by_id(spill_id)
                if spill is None:
                    raise ValueError(f"Spill with ID '{spill_id}' not found.")
                # Fallback centroid if not provided
                detection_lon = detection_lon if detection_lon is not None else 72.50
                detection_lat = detection_lat if detection_lat is not None else 21.00
                detection_time = detection_time or spill.detected_at or scene.captured_at
            else:
                detection_lon = detection_lon if detection_lon is not None else 72.50
                detection_lat = detection_lat if detection_lat is not None else 21.00
                detection_time = detection_time or scene.captured_at

        # Ensure UTC timezone
        if detection_time.tzinfo is None:
            detection_time = detection_time.replace(tzinfo=timezone.utc)

        # Idempotency fingerprint
        fingerprint = _compute_fingerprint(
            scene_id=scene_id,
            spill_id=spill_id,
            lon=detection_lon,
            lat=detection_lat,
            det_time=detection_time,
            window_hours=window_hours,
            n_scenarios=n_scenarios,
            stokes=stokes_mode,
        )

        # Check existing run
        if not force_rerun:
            existing = await self.drift_repo.get_by_fingerprint(fingerprint)
            if existing and existing.status == DriftStatusEnum.completed:
                log.info("Returning cached drift run %s (fingerprint=%s)", existing.id, fingerprint)
                summary = existing.result_summary or {}
                origin = summary.get("origin_estimate")
                contours = summary.get("contours", [])
                heatmap_sum = summary.get("heatmap_summary")

                exec_time = (time.perf_counter() - start_clock) * 1000.0
                return {
                    "run_id": existing.id,
                    "scene_id": scene_id,
                    "spill_id": spill_id,
                    "status": "completed",
                    "run_fingerprint": fingerprint,
                    "origin_estimate": OriginEstimate(**origin) if origin else None,
                    "contours": [ConfidenceContour(**c) for c in contours],
                    "heatmap_summary": HeatmapSummary(**heatmap_sum) if heatmap_sum else None,
                    "output_storage_uri": existing.output_storage_uri,
                    "execution_time_ms": exec_time,
                    "message": "Drift reconstruction retrieved from cache (idempotent run).",
                }

        model_params = {
            "window_hours": window_hours,
            "n_scenarios": n_scenarios,
            "stokes_mode": stokes_mode,
            "detection_point": {"lon": detection_lon, "lat": detection_lat},
            "detection_time": detection_time.isoformat(),
        }

        # Create drift_runs record in status 'running'
        drift_run = await self.drift_repo.create_drift_run(
            scene_id=scene_id,
            spill_id=spill_id,
            simulation_version=SIMULATION_VERSION,
            model_parameters=model_params,
            run_fingerprint=fingerprint,
            status=DriftStatusEnum.running,
        )
        await self.session.commit()

        # Prepare forcing files
        wind_path = "data/forcing/wind_synthetic.nc"
        current_path = "data/forcing/current_synthetic.nc"
        if not os.path.exists(wind_path):
            make_synthetic_wind(wind_path)
        if not os.path.exists(current_path):
            make_synthetic_current(current_path)

        out_dir = f"data/ensemble_outputs/{drift_run.id}"
        os.makedirs(out_dir, exist_ok=True)

        try:
            # Generate perturbed scenarios
            scenarios = sample_scenarios(
                det_lon=detection_lon,
                det_lat=detection_lat,
                det_time=detection_time,
                window_hours=window_hours,
                n=n_scenarios,
                seed=42,
            )

            # Spatial boundaries for heatmap (padding ~ 1.5 degrees)
            lon_bounds = (detection_lon - 1.5, detection_lon + 1.5)
            lat_bounds = (detection_lat - 1.5, detection_lat + 1.5)

            # Run backward ensemble pipeline
            results = full_backward_pipeline(
                scenarios=scenarios,
                wind=wind_path,
                current=current_path,
                wave=None,
                lon_bounds=lon_bounds,
                lat_bounds=lat_bounds,
                outdir=out_dir,
                stokes=stokes_mode,
                n_workers=2,
            )

            grid = results["grid"]
            lon_bins = results["lon_bins"]
            lat_bins = results["lat_bins"]
            peak = results["peak"]
            raw_contours = results["contours"]

            # Format confidence contours
            formatted_contours = []
            for lvl in (0.50, 0.75, 0.90):
                if lvl in raw_contours:
                    mask = raw_contours[lvl]
                    poly_coords = contour_to_polygon(mask, lon_bins, lat_bins)
                    if poly_coords:
                        formatted_contours.append({
                            "level": lvl,
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": poly_coords,
                            },
                        })

            release_start = detection_time - timedelta(hours=window_hours)
            origin_estimate = {
                "peak_lon": peak["lon"],
                "peak_lat": peak["lat"],
                "peak_prob": peak["prob"],
                "release_window_start": release_start.isoformat(),
                "release_window_end": detection_time.isoformat(),
            }

            heatmap_summary = {
                "lon_min": float(lon_bounds[0]),
                "lon_max": float(lon_bounds[1]),
                "lat_min": float(lat_bounds[0]),
                "lat_max": float(lat_bounds[1]),
                "resolution_deg": 0.02,
                "grid_shape": list(grid.shape),
                "total_runs": n_scenarios,
                "successful_runs": len(results["files"]),
            }

            result_summary = {
                "origin_estimate": origin_estimate,
                "contours": formatted_contours,
                "heatmap_summary": heatmap_summary,
            }

            output_uri = f"minio://payodi-drift-runs/{drift_run.id}/ensemble_summary.json"

            # Update drift run status to completed
            await self.drift_repo.update_status(
                drift_run.id,
                status=DriftStatusEnum.completed,
                result_summary=result_summary,
                output_storage_uri=output_uri,
                completed_at=datetime.now(timezone.utc),
            )

            # Append audit log
            await self.audit.append(
                actor_type="system",
                actor_id=actor_id,
                action="create",
                entity_type="drift_runs",
                entity_id=drift_run.id,
                request_id=request_id,
                after={
                    "status": DriftStatusEnum.completed.value,
                    "peak_origin": [peak["lon"], peak["lat"]],
                    "confidence_levels": [0.5, 0.75, 0.9],
                },
                metadata={
                    "scene_id": str(scene_id),
                    "spill_id": str(spill_id) if spill_id else None,
                    "simulation_version": SIMULATION_VERSION,
                    "runs_count": len(results["files"]),
                },
            )

            await self.session.commit()

            exec_time = (time.perf_counter() - start_clock) * 1000.0

            return {
                "run_id": drift_run.id,
                "scene_id": scene_id,
                "spill_id": spill_id,
                "status": "completed",
                "run_fingerprint": fingerprint,
                "origin_estimate": OriginEstimate(
                    peak_lon=peak["lon"],
                    peak_lat=peak["lat"],
                    peak_prob=peak["prob"],
                    release_window_start=release_start,
                    release_window_end=detection_time,
                ),
                "contours": [ConfidenceContour(**c) for c in formatted_contours],
                "heatmap_summary": HeatmapSummary(**heatmap_summary),
                "output_storage_uri": output_uri,
                "execution_time_ms": exec_time,
                "message": f"Successfully completed backward drift reconstruction ({len(results['files'])} simulations).",
            }

        except Exception as exc:
            log.exception("Backward drift reconstruction failed for run %s: %s", drift_run.id, exc)
            await self.drift_repo.update_status(
                drift_run.id,
                status=DriftStatusEnum.failed,
                error_message=str(exc),
                completed_at=datetime.now(timezone.utc),
            )
            await self.session.commit()
            raise

    async def score_candidate_vessels(
        self,
        scene_id: UUID,
        spill_id: Optional[UUID],
        detection_lon: float,
        detection_lat: float,
        detection_time: datetime,
        candidates: List[ForwardAttributionCandidateRequest],
        threshold_km: float = 30.0,
    ) -> ForwardAttributionResponse:
        """
        Run forward simulation from each candidate vessel's known track position,
        computing distance to detected slick centroid and overall attribution ranking.
        """
        wind_path = "data/forcing/wind_synthetic.nc"
        current_path = "data/forcing/current_synthetic.nc"
        if not os.path.exists(wind_path):
            make_synthetic_wind(wind_path)
        if not os.path.exists(current_path):
            make_synthetic_current(current_path)

        out_dir = f"data/forward_outputs/{scene_id}"
        os.makedirs(out_dir, exist_ok=True)

        scored_candidates: List[CandidateScoreResponse] = []

        for cand in candidates:
            cand_dict = {
                "mmsi": cand.mmsi,
                "vessel_name": cand.vessel_name or f"MMSI_{cand.mmsi}",
                "lon": cand.vessel_lon,
                "lat": cand.vessel_lat,
                "release_time": cand.release_time,
                "detection_time": detection_time,
                "oil_type": cand.oil_type,
            }

            res = score_vessel(
                candidate=cand_dict,
                detection_lon=detection_lon,
                detection_lat=detection_lat,
                wind=wind_path,
                current=current_path,
                outdir=out_dir,
                threshold_km=threshold_km,
            )

            scored_candidates.append(
                CandidateScoreResponse(
                    mmsi=res["mmsi"],
                    vessel_name=res.get("vessel_name", ""),
                    forward_score=res["forward_score"],
                    distance_km=res.get("distance_km"),
                    predicted_centroid=list(res["predicted_centroid"]) if res.get("predicted_centroid") else None,
                    release_time=res.get("release_time", str(cand.release_time)),
                    oil_type=res.get("oil_type", cand.oil_type),
                    error=res.get("error"),
                )
            )

        ranked = rank_candidates([c.model_dump() for c in scored_candidates])
        classification = classify_attribution(ranked)

        return ForwardAttributionResponse(
            scene_id=scene_id,
            spill_id=spill_id,
            ranked_candidates=scored_candidates,
            outcome=classification["outcome"],
            reason=classification["reason"],
        )
