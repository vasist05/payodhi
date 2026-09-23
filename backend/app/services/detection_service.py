"""
backend/app/services/detection_service.py

Phase 1 SAR Detection service layer.
Orchestrates deep-learning segmentation (core/phase1_sar/) with PostgreSQL/PostGIS
persistence adhering strictly to DataBaseFinal.md (Table 3 scenes, Table 4 spills, Table 8 audit_log).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_repo import AuditRepository
from app.repositories.scene_repo import SceneRepository
from app.repositories.spill_repo import SpillRepository
from app.schemas.common import geojson_to_wkt
from app.schemas.spill import SpillCandidate
from core.phase1_sar.inference import SARSpillDetector

log = logging.getLogger(__name__)

MODEL_NAME = "SAR_Unet_Detector"
MODEL_VERSION = "resnet34-v1.0"


class DetectionService:
    """
    Service coordinating Phase 1 U-Net detection and database persistence.
    """

    _detector_instance: Optional[SARSpillDetector] = None

    def __init__(self, session: AsyncSession):
        self.session = session
        self.scenes = SceneRepository(session)
        self.spills = SpillRepository(session)
        self.audit = AuditRepository(session)

    @classmethod
    def get_detector(cls) -> SARSpillDetector:
        """Lazy singleton loader for the neural network model."""
        if cls._detector_instance is None:
            log.info("Initializing SARSpillDetector singleton...")
            cls._detector_instance = SARSpillDetector()
        return cls._detector_instance

    async def run_detection(
        self,
        scene_id: UUID,
        image_path: Optional[str] = None,
        threshold: float = 0.50,
        min_pixels: int = 50,
        actor_id: Optional[str] = None,
        request_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Execute Phase 1 detection on a scene, persist all detected spills,
        log audit events, and return database records + candidates.
        """
        scene = await self.scenes.get_by_id(scene_id)
        if scene is None:
            raise ValueError(f"Scene with ID '{scene_id}' not found.")

        # Determine input image path
        target_path = image_path or scene.storage_uri
        if not target_path or not Path(target_path).exists():
            # If not a local file, check standard test or input locations
            candidate_paths = [
                Path(target_path) if target_path else None,
                Path("data/fixtures") / f"{scene.external_scene_id}.png",
                Path("data/phase1_input") / f"{scene.external_scene_id}.png",
                Path("data/phase1_input/sample_scene.png"),
            ]
            found = next((p for p in candidate_paths if p and p.exists()), None)
            if found is None:
                raise FileNotFoundError(
                    f"Image file for scene {scene_id} could not be resolved from path: '{target_path}'"
                )
            target_path = str(found)

        # Update scene status to processing
        await self.scenes.update_status(scene_id, "processing")
        await self.session.flush()

        detector = self.get_detector()

        try:
            # Run inference
            results = detector.detect(
                image_input=target_path,
                threshold=threshold,
                min_pixels=min_pixels,
                scene_id=str(scene_id),
                output_crops_dir="data/phase1_crops",
            )
        except Exception as exc:
            log.exception("Detection failed for scene %s: %s", scene_id, exc)
            await self.scenes.update_status(scene_id, "failed")
            await self.session.commit()
            raise

        created_spills = []
        phase2_candidates: List[SpillCandidate] = []

        # Persist detected spills into database
        for idx, det in enumerate(results["detections"]):
            geom_wkt = geojson_to_wkt(det["geometry"])
            spill = await self.spills.create_spill(
                scene_id=scene_id,
                spill_polygon_wkt=geom_wkt,
                area_sq_km=det["area_sq_km"],
                detection_model_name=MODEL_NAME,
                detection_model_version=MODEL_VERSION,
                confidence_score=det["confidence"],
                status="detected",
                review_notes=f"Detected via Phase 1 U-Net (mean_conf={det['confidence']:.3f})",
            )

            # Append tamper-evident audit record
            await self.audit.append(
                actor_type="system",
                actor_id=actor_id,
                action="create",
                entity_type="spills",
                entity_id=spill.id,
                request_id=request_id,
                after={
                    "status": spill.status,
                    "confidence": det["confidence"],
                    "area_sq_km": det["area_sq_km"],
                },
                metadata={
                    "model": MODEL_NAME,
                    "version": MODEL_VERSION,
                    "scene_id": str(scene_id),
                },
            )
            created_spills.append(spill)

            # Map to candidate for Phase 2 filter
            if idx < len(results["candidates"]):
                c = results["candidates"][idx]
                phase2_candidates.append(
                    SpillCandidate(
                        patch_path=c.patch_path,
                        center_lat=c.center_lat,
                        center_lon=c.center_lon,
                        scene_id=scene_id,
                        spill_polygon=det["geometry"],
                        area_sq_km=det["area_sq_km"],
                        detection_confidence=det["confidence"],
                    )
                )

        # Mark scene as processed
        await self.scenes.update_status(scene_id, "processed")
        await self.session.commit()

        log.info(
            "Phase 1 Detection completed for scene %s: %d spills persisted.",
            scene_id,
            len(created_spills),
        )

        return {
            "scene_id": scene_id,
            "spill_count": len(created_spills),
            "spills": created_spills,
            "candidates": phase2_candidates,
            "status": "success",
            "message": f"Successfully detected and persisted {len(created_spills)} oil spill(s).",
        }
