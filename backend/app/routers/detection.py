"""
backend/app/routers/detection.py

FastAPI router for Phase 1 SAR Oil Spill Detection.
Provides endpoints for executing U-Net detection on scenes and seamless end-to-end
detection + Phase-2 false-positive filtering.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.detection import DetectionRunRequest, DetectionRunResponse
from app.schemas.spill import SpillFilterBatchResponse, SpillResponse
from app.services.detection_service import DetectionService
from app.services.filter_service import FilterService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/detection", tags=["detection"])


@router.post("/detect", response_model=DetectionRunResponse)
async def detect_spills_in_scene(
    payload: DetectionRunRequest,
    session: AsyncSession = Depends(get_session),
) -> DetectionRunResponse:
    """
    Run Phase 1 U-Net detection on a satellite SAR scene, persist detected spills
    in PostgreSQL/PostGIS (spills table, status='detected'), log to audit_log,
    and output candidate patches for downstream verification.
    """
    svc = DetectionService(session)
    try:
        res = await svc.run_detection(
            scene_id=payload.scene_id,
            image_path=payload.image_path,
            threshold=payload.threshold,
            min_pixels=payload.min_pixels,
        )
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        log.exception("Detection failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Detection execution failed: {exc}")

    return DetectionRunResponse(
        scene_id=res["scene_id"],
        spill_count=res["spill_count"],
        spills=[SpillResponse.model_validate(s, from_attributes=True) for s in res["spills"]],
        candidates=res["candidates"],
        status=res["status"],
        message=res["message"],
    )


@router.post("/detect-and-filter")
async def detect_and_filter_pipeline(
    payload: DetectionRunRequest,
    filter_mode: Literal["sar_only", "sar_speed", "sar_uv"] = "sar_uv",
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Unified end-to-end pipeline:
    1. Phase 1: Detect candidate oil slicks using base U-Net model.
    2. Phase 2: Immediately verify candidate patches against the trained SAR-UV False-Positive Filter.
    Returns confirmed spills, rejected lookalikes, and audit trail.
    """
    det_svc = DetectionService(session)
    det_res = await det_svc.run_detection(
        scene_id=payload.scene_id,
        image_path=payload.image_path,
        threshold=payload.threshold,
        min_pixels=payload.min_pixels,
    )

    candidates = det_res["candidates"]
    if not candidates:
        return {
            "scene_id": str(payload.scene_id),
            "spill_count_initial": 0,
            "confirmed_spills": [],
            "rejected_lookalikes": [],
            "message": "No spill candidates detected in SAR scene.",
        }

    # Pass directly to Phase 2 FilterService
    filter_svc = FilterService(session, mode=filter_mode)
    filter_res = await filter_svc.filter_batch([c.model_dump() for c in candidates])

    return {
        "scene_id": str(payload.scene_id),
        "spill_count_initial": det_res["spill_count"],
        "confirmed_count": len(filter_res["confirmed"]),
        "rejected_count": len(filter_res["rejected"]),
        "confirmed_spills": [
            SpillResponse.model_validate(s, from_attributes=True) for s in filter_res["confirmed"]
        ],
        "rejected_lookalikes": [
            SpillResponse.model_validate(s, from_attributes=True) for s in filter_res["rejected"]
        ],
        "filter_mode": filter_res["model_mode"],
        "calibration_temperature": filter_res["calibration_temperature"],
    }
