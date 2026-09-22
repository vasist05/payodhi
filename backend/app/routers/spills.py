"""
backend/app/routers/spills.py

FastAPI router for Spill detections and Phase-2 batch filtering.
Adheres strictly to DataBaseFinal.md contracts; wind context arrives via scene join.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.spill_repo import SpillRepository
from app.schemas.spill import (
    SpillFilterBatchRequest,
    SpillFilterBatchResponse,
    SpillResponse,
)
from app.services.filter_service import FilterService

router = APIRouter(prefix="/api/v1/spills", tags=["spills"])


@router.post("/filter", response_model=SpillFilterBatchResponse)
async def filter_candidates(
    payload: SpillFilterBatchRequest,
    mode: Literal["sar_only", "sar_speed", "sar_uv"] = "sar_uv",
    session: AsyncSession = Depends(get_session),
) -> SpillFilterBatchResponse:
    """
    Batch evaluate proposed candidate spill regions through Phase-2 False-Positive Filter,
    persist confirmed/rejected records in `spills`, and append cryptographic audit logs.
    """
    svc = FilterService(session, mode=mode)
    out = await svc.filter_batch([c.model_dump() for c in payload.candidates])
    return SpillFilterBatchResponse(
        confirmed=[SpillResponse.model_validate(s, from_attributes=True) for s in out["confirmed"]],
        rejected=[SpillResponse.model_validate(s, from_attributes=True) for s in out["rejected"]],
        failed=out["failed"],
        model_mode=out["model_mode"],
        calibration_temperature=out["calibration_temperature"],
    )


@router.get("", response_model=list[SpillResponse])
async def list_spills(
    status: str | None = Query(None, pattern="^(detected|under_review|confirmed|rejected)$"),
    scene_id: UUID | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[SpillResponse]:
    """Query spills with eager-loaded scene wind context."""
    repo = SpillRepository(session)
    rows = await repo.list_with_scene(status=status, scene_id=scene_id, limit=limit, offset=offset)
    return [SpillResponse.model_validate(r, from_attributes=True) for r in rows]


@router.get("/{spill_id}", response_model=SpillResponse)
async def get_spill(
    spill_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> SpillResponse:
    """Retrieve detailed spill record with attached scene wind context."""
    repo = SpillRepository(session)
    row = await repo.get_with_scene(spill_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Spill detection not found")
    return SpillResponse.model_validate(row, from_attributes=True)
