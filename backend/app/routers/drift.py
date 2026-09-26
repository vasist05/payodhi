"""
backend/app/routers/drift.py

FastAPI router for Phase 3 Hydrodynamic Drift Modeling & Origin Reconstruction.
Provides endpoints for backward trajectory simulation, forward vessel release verification,
and querying run outputs.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.drift_repo import DriftRepository
from app.schemas.drift import (
    DriftRunRequest,
    DriftRunResponse,
    ForwardAttributionRequest,
    ForwardAttributionResponse,
)
from app.services.drift_service import DriftService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/drift", tags=["drift"])


@router.post("/backward", response_model=DriftRunResponse)
async def run_backward_drift_simulation(
    payload: DriftRunRequest,
    session: AsyncSession = Depends(get_session),
) -> DriftRunResponse:
    """
    Execute Phase 3 backward ensemble drift simulation for an oil spill candidate.
    Generates 2D probability origin heatmap, cumulative confidence contours (50%, 75%, 90%),
    and persists record in drift_runs table with SHA-256 fingerprint deduplication.
    """
    svc = DriftService(session)
    try:
        res = await svc.run_backward_reconstruction(
            scene_id=payload.scene_id,
            spill_id=payload.spill_id,
            detection_lon=payload.detection_lon,
            detection_lat=payload.detection_lat,
            detection_time=payload.detection_time,
            window_hours=payload.window_hours,
            n_scenarios=payload.n_scenarios,
            stokes_mode=payload.stokes_mode,
            force_rerun=payload.force_rerun,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        log.exception("Drift simulation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Drift simulation execution failed: {exc}")

    return DriftRunResponse(
        run_id=res["run_id"],
        scene_id=res["scene_id"],
        spill_id=res["spill_id"],
        status=res["status"],
        run_fingerprint=res["run_fingerprint"],
        origin_estimate=res["origin_estimate"],
        contours=res["contours"],
        heatmap_summary=res["heatmap_summary"],
        output_storage_uri=res["output_storage_uri"],
        execution_time_ms=res["execution_time_ms"],
        message=res["message"],
    )


@router.post("/forward-attribution", response_model=ForwardAttributionResponse)
async def score_vessel_attributions(
    payload: ForwardAttributionRequest,
    session: AsyncSession = Depends(get_session),
) -> ForwardAttributionResponse:
    """
    Execute Phase 3 forward drift simulation from candidate vessel release coordinates,
    scoring each vessel's agreement with the detected spill location.
    """
    svc = DriftService(session)
    try:
        res = await svc.score_candidate_vessels(
            scene_id=payload.scene_id,
            spill_id=payload.spill_id,
            detection_lon=payload.detection_lon,
            detection_lat=payload.detection_lat,
            detection_time=payload.detection_time,
            candidates=payload.candidates,
            threshold_km=payload.threshold_km,
        )
    except Exception as exc:
        log.exception("Forward attribution scoring failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Attribution scoring failed: {exc}")

    return res


@router.get("/runs/{run_id}")
async def get_drift_run_by_id(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Retrieve full drift run metadata, status, and summary."""
    repo = DriftRepository(session)
    drift_run = await repo.get_with_relations(run_id)
    if drift_run is None:
        raise HTTPException(status_code=404, detail=f"Drift run with ID '{run_id}' not found.")

    return {
        "id": str(drift_run.id),
        "scene_id": str(drift_run.scene_id),
        "spill_id": str(drift_run.spill_id) if drift_run.spill_id else None,
        "vessel_id": str(drift_run.vessel_id),
        "simulation_version": drift_run.simulation_version,
        "status": drift_run.status.value,
        "run_fingerprint": drift_run.run_fingerprint,
        "started_at": drift_run.started_at.isoformat() if drift_run.started_at else None,
        "completed_at": drift_run.completed_at.isoformat() if drift_run.completed_at else None,
        "result_summary": drift_run.result_summary,
        "output_storage_uri": drift_run.output_storage_uri,
        "error_message": drift_run.error_message,
    }


@router.get("/scene/{scene_id}")
async def list_drift_runs_for_scene(
    scene_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list:
    """List all drift simulations executed for a satellite scene."""
    repo = DriftRepository(session)
    runs = await repo.list_by_scene(scene_id)
    return [
        {
            "id": str(r.id),
            "scene_id": str(r.scene_id),
            "spill_id": str(r.spill_id) if r.spill_id else None,
            "status": r.status.value,
            "run_fingerprint": r.run_fingerprint,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]
