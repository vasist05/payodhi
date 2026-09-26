"""
backend/app/routers/pipeline.py

FastAPI router for the Unified Multi-Phase Pipeline (Phase 1 -> Phase 2 -> Phase 3).
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.pipeline import IntegratedPipelineRequest, IntegratedPipelineResponse
from app.services.pipeline_service import IntegratedPipelineService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.post("/end-to-end", response_model=IntegratedPipelineResponse)
async def run_end_to_end_pipeline(
    payload: IntegratedPipelineRequest,
    session: AsyncSession = Depends(get_session),
) -> IntegratedPipelineResponse:
    """
    Execute the entire automated pipeline:
      1. Phase 1: SAR U-Net Segmentation Detection
      2. Phase 2: SAR-UV False-Positive Filtering (ERA5 Wind Vector Integration)
      3. Phase 3: Hydrodynamic Backward Drift Simulation & Origin Probability Reconstruction
    """
    svc = IntegratedPipelineService(session)
    try:
        res = await svc.execute_full_pipeline(
            scene_id=payload.scene_id,
            image_path=payload.image_path,
            detection_threshold=payload.detection_threshold,
            min_pixels=payload.min_pixels,
            filter_mode=payload.filter_mode,
            drift_window_hours=payload.drift_window_hours,
            n_drift_scenarios=payload.n_drift_scenarios,
            stokes_mode=payload.stokes_mode,
        )
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        log.exception("End-to-end pipeline execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}")

    return res
