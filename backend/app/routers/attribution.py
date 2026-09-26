import json
import logging
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.attribution_score import AttributionScore
from app.db.models.cpa_event import CpaEvent
from app.db.session import get_session
from app.schemas.attribution import (
    AttributionRunRequest,
    AttributionScoreResponse,
    CpaEventResponse,
)
from app.services.attribution_pipeline import run_attribution

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run/{drift_run_id}")
async def run_attribution_endpoint(
    drift_run_id: UUID,
    body: AttributionRunRequest = AttributionRunRequest(),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Trigger 7-pillar evidential attribution pipeline for a drift run."""
    try:
        result = await run_attribution(
            session=session,
            drift_run_id=drift_run_id,
            scoring_version=body.scoring_version,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Pipeline error during attribution execution: %s", e)
        raise HTTPException(status_code=500, detail="pipeline_error")


@router.get("/{drift_run_id}", response_model=AttributionScoreResponse)
async def get_latest_attribution_score(
    drift_run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> AttributionScoreResponse:
    """Fetch latest attribution score for a given drift run."""
    stmt = (
        select(AttributionScore)
        .where(AttributionScore.drift_run_id == drift_run_id)
        .order_by(AttributionScore.calculated_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="attribution_score_not_found")
    return score


@router.get("/{drift_run_id}/history", response_model=List[AttributionScoreResponse])
async def get_attribution_history(
    drift_run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> List[AttributionScoreResponse]:
    """Fetch all historical attribution scores for a drift run."""
    stmt = (
        select(AttributionScore)
        .where(AttributionScore.drift_run_id == drift_run_id)
        .order_by(AttributionScore.calculated_at.desc())
    )
    result = await session.execute(stmt)
    scores = result.scalars().all()
    return list(scores)


@router.get("/{drift_run_id}/cpa-events", response_model=List[CpaEventResponse])
async def get_cpa_events(
    drift_run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> List[CpaEventResponse]:
    """Fetch Closest Point of Approach (CPA) events with GeoJSON coordinates."""
    stmt = select(
        CpaEvent.id,
        CpaEvent.drift_run_id,
        CpaEvent.vessel_id,
        CpaEvent.min_distance_m,
        CpaEvent.cpa_timestamp,
        CpaEvent.tcpa_seconds,
        func.ST_AsGeoJSON(CpaEvent.vessel_position_at_cpa).label("vessel_geojson"),
        func.ST_AsGeoJSON(CpaEvent.slick_position_at_cpa).label("slick_geojson"),
        CpaEvent.created_at,
    ).where(CpaEvent.drift_run_id == drift_run_id)

    result = await session.execute(stmt)
    rows = result.all()

    events: List[CpaEventResponse] = []
    for row in rows:
        vessel_geojson = json.loads(row.vessel_geojson) if row.vessel_geojson else {}
        slick_geojson = json.loads(row.slick_geojson) if row.slick_geojson else {}
        events.append(
            CpaEventResponse(
                id=row.id,
                drift_run_id=row.drift_run_id,
                vessel_id=row.vessel_id,
                min_distance_m=row.min_distance_m,
                cpa_timestamp=row.cpa_timestamp,
                tcpa_seconds=row.tcpa_seconds,
                vessel_position_at_cpa=vessel_geojson,
                slick_position_at_cpa=slick_geojson,
                created_at=row.created_at,
            )
        )
    return events
