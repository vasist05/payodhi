import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ais_gap import AisGap
from app.db.models.attribution_score import AttributionScore
from app.db.models.audit_log import AuditLog
from app.db.models.cpa_event import CpaEvent
from app.db.models.drift_run import DriftRun
from app.db.models.enums import ActorTypeEnum, AuditActionEnum, VerdictEnum
from app.db.models.track import Track
from app.db.models.vessel import Vessel
from app.db.models.vessel_static_history import VesselStaticHistory

logger = logging.getLogger(__name__)


async def load_vessel_track(
    session: AsyncSession,
    vessel_id: UUID,
    scene_time: datetime,
    window_hours: int = 6,
) -> List[Dict[str, Any]]:
    """Load vessel AIS tracks within a time window around scene_time."""
    if scene_time.tzinfo is None:
        scene_time = scene_time.replace(tzinfo=timezone.utc)

    start_time = scene_time - timedelta(hours=window_hours)
    end_time = scene_time + timedelta(hours=window_hours)

    stmt = (
        select(
            func.ST_Y(Track.position).label("lat"),
            func.ST_X(Track.position).label("lon"),
            Track.recorded_at.label("time"),
            Track.speed_knots,
            Track.course_degrees,
            Track.heading_degrees,
        )
        .where(
            Track.vessel_id == vessel_id,
            Track.recorded_at.between(start_time, end_time),
        )
        .order_by(Track.recorded_at.asc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    tracks: List[Dict[str, Any]] = []
    for r in rows:
        tracks.append({
            "lat": float(r.lat),
            "lon": float(r.lon),
            "time": r.time,
            "speed_knots": float(r.speed_knots) if r.speed_knots is not None else 0.0,
            "course_degrees": float(r.course_degrees) if r.course_degrees is not None else 0.0,
            "heading_degrees": float(r.heading_degrees) if r.heading_degrees is not None else None,
        })
    return tracks


async def load_drift_trajectory(
    session: AsyncSession,
    drift_run_id: UUID,
) -> List[Dict[str, Any]]:
    """Load simulated drift trajectory points from drift_runs.result_summary."""
    stmt = select(DriftRun.result_summary).where(DriftRun.id == drift_run_id)
    result = await session.execute(stmt)
    summary = result.scalar_one_or_none()

    if not summary or not isinstance(summary, dict):
        return []

    geoms = summary.get("particle_geometries")
    if not geoms or not isinstance(geoms, list):
        return []

    trajectory: List[Dict[str, Any]] = []
    for p in geoms:
        if isinstance(p, dict) and "lat" in p and "lon" in p:
            t = p.get("time")
            if isinstance(t, str):
                try:
                    t = datetime.fromisoformat(t)
                except Exception:
                    pass
            trajectory.append({
                "lat": float(p["lat"]),
                "lon": float(p["lon"]),
                "time": t,
            })
    return trajectory


async def load_vessel_meta(
    session: AsyncSession,
    vessel_id: UUID,
) -> Dict[str, Any]:
    """Load vessel type and deadweight tonnage metadata."""
    stmt = select(Vessel.vessel_type, Vessel.deadweight_tonnage).where(Vessel.id == vessel_id)
    result = await session.execute(stmt)
    row = result.first()

    if not row:
        return {"vessel_type": "unknown", "deadweight_tonnage": None}

    v_type = row[0].value if hasattr(row[0], "value") else str(row[0])
    dwt = float(row[1]) if row[1] is not None else None
    return {"vessel_type": v_type, "deadweight_tonnage": dwt}


async def load_ais_gaps(
    session: AsyncSession,
    vessel_id: UUID,
    scene_time: datetime,
    window_hours: int = 6,
) -> List[Dict[str, Any]]:
    """Load AIS gaps for the vessel within time window."""
    if scene_time.tzinfo is None:
        scene_time = scene_time.replace(tzinfo=timezone.utc)

    start_time = scene_time - timedelta(hours=window_hours)
    end_time = scene_time + timedelta(hours=window_hours)

    stmt = (
        select(
            AisGap.gap_start,
            AisGap.gap_end,
            AisGap.gap_duration_min,
            AisGap.is_open_water,
            func.ST_Y(AisGap.gap_center).label("gap_center_lat"),
            func.ST_X(AisGap.gap_center).label("gap_center_lon"),
        )
        .where(
            AisGap.vessel_id == vessel_id,
            AisGap.gap_start.between(start_time, end_time),
        )
        .order_by(AisGap.gap_start.asc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    gaps: List[Dict[str, Any]] = []
    for r in rows:
        gaps.append({
            "gap_start": r.gap_start,
            "gap_end": r.gap_end,
            "gap_duration_min": float(r.gap_duration_min) if r.gap_duration_min is not None else 0.0,
            "is_open_water": bool(r.is_open_water),
            "gap_center_lat": float(r.gap_center_lat) if r.gap_center_lat is not None else None,
            "gap_center_lon": float(r.gap_center_lon) if r.gap_center_lon is not None else None,
        })
    return gaps


async def load_draft_history(
    session: AsyncSession,
    vessel_id: UUID,
    spill_time: datetime,
    window_hours: int = 48,
) -> List[Dict[str, Any]]:
    """Load vessel static draft history around spill time."""
    if spill_time.tzinfo is None:
        spill_time = spill_time.replace(tzinfo=timezone.utc)

    start_time = spill_time - timedelta(hours=window_hours)
    end_time = spill_time + timedelta(hours=window_hours)

    stmt = (
        select(
            VesselStaticHistory.recorded_at,
            VesselStaticHistory.draft_meters,
        )
        .where(
            VesselStaticHistory.vessel_id == vessel_id,
            VesselStaticHistory.recorded_at.between(start_time, end_time),
            VesselStaticHistory.draft_meters.isnot(None),
        )
        .order_by(VesselStaticHistory.recorded_at.asc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "recorded_at": r.recorded_at,
            "draft_meters": float(r.draft_meters),
        }
        for r in rows
    ]


async def load_port_polygons(
    session: Optional[AsyncSession] = None,
) -> List[Any]:
    """Read port/anchorage polygons from config/port_polygons.json. Create as [] if missing."""
    possible_paths = [
        Path("config/port_polygons.json"),
        Path(__file__).resolve().parent.parent.parent.parent / "config" / "port_polygons.json",
        Path(__file__).resolve().parent.parent / "config" / "port_polygons.json",
    ]

    for p in possible_paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Error reading port_polygons.json: %s", e)
                return []

    target_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "port_polygons.json"
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("[]\n", encoding="utf-8")
    except Exception as e:
        logger.warning("Could not create port_polygons.json: %s", e)

    return []


async def persist_cpa_event(
    session: AsyncSession,
    drift_run_id: UUID,
    vessel_id: UUID,
    cpa_result: Dict[str, Any],
) -> UUID:
    """Insert CPA event record into cpa_events table."""
    v_pt = cpa_result.get("vessel_point") or {}
    d_pt = cpa_result.get("drift_point") or {}
    v_lon = float(v_pt.get("lon", 0.0))
    v_lat = float(v_pt.get("lat", 0.0))
    d_lon = float(d_pt.get("lon", 0.0))
    d_lat = float(d_pt.get("lat", 0.0))

    cpa_ts = cpa_result.get("cpa_timestamp")
    if isinstance(cpa_ts, str):
        cpa_ts = datetime.fromisoformat(cpa_ts)
    elif cpa_ts is None:
        cpa_ts = datetime.now(timezone.utc)
    elif cpa_ts.tzinfo is None:
        cpa_ts = cpa_ts.replace(tzinfo=timezone.utc)

    min_dist = max(0.0, float(cpa_result.get("min_distance_m", 0.0) or 0.0))
    tcpa_sec = float(cpa_result.get("tcpa_seconds", 0.0) or 0.0)

    event = CpaEvent(
        drift_run_id=drift_run_id,
        vessel_id=vessel_id,
        min_distance_m=Decimal(str(round(min_dist, 2))),
        cpa_timestamp=cpa_ts,
        tcpa_seconds=Decimal(str(round(tcpa_sec, 2))),
        vessel_position_at_cpa=func.ST_SetSRID(func.ST_MakePoint(v_lon, v_lat), 4326),
        slick_position_at_cpa=func.ST_SetSRID(func.ST_MakePoint(d_lon, d_lat), 4326),
    )
    session.add(event)
    await session.flush()
    return event.id


async def persist_attribution_score(
    session: AsyncSession,
    drift_run_id: UUID,
    scoring_version: str,
    pillars: Dict[str, Dict[str, Any]],
    fusion_result: Dict[str, Any],
    verdict_result: Dict[str, Any],
) -> UUID:
    """Insert or retrieve attribution score in attribution_scores table."""
    p1 = pillars.get("pillar1_cpa", {})
    p2 = pillars.get("pillar2_dark", {})
    p3 = pillars.get("pillar3_loiter", {})
    p4 = pillars.get("pillar4_capacity", {})
    p5 = pillars.get("pillar5_draft", {})
    p6 = pillars.get("pillar6_permutation", {})
    p7 = pillars.get("pillar7_sensitivity", {})

    cpa_score_val = max(0.0, min(1.0, float(p1.get("cpa_score", 0.0) or 0.0)))
    dark_score_val = max(0.0, min(1.0, float(p2.get("dark_vessel_score", 0.0) or 0.0)))
    loiter_score_val = max(0.0, min(1.0, float(p3.get("loitering_score", 0.0) or 0.0)))
    cap_mult_val = 0 if int(round(float(p4.get("db_multiplier", 1.0)))) == 0 else 1
    draft_score_val = max(0.0, min(1.0, float(p5.get("draft_change_score", 0.0) or 0.0)))
    p_val = max(0.0, min(1.0, float(p6.get("p_value", 1.0) or 1.0)))
    stab_val = max(0.0, min(1.0, float(p7.get("stability_index", 0.0) or 0.0)))
    total_score_val = max(0.0, min(100.0, float(fusion_result.get("total_score", 0.0) or 0.0)))

    raw_verdict = verdict_result.get("db_verdict") or verdict_result.get("verdict") or "insufficient_evidence"
    if isinstance(raw_verdict, str):
        verdict_enum_val = VerdictEnum(raw_verdict.lower())
    elif isinstance(raw_verdict, VerdictEnum):
        verdict_enum_val = raw_verdict
    else:
        verdict_enum_val = VerdictEnum.insufficient_evidence

    explanation_payload = {
        "pillar1_cpa": p1.get("explanation") or p1.get("reason"),
        "pillar2_dark": p2.get("reason"),
        "pillar3_loiter": p3.get("reason"),
        "pillar4_capacity": p4.get("reason"),
        "pillar5_draft": p5.get("reason"),
        "pillar6_permutation": p6.get("reason"),
        "pillar7_sensitivity": p7.get("reason"),
        "verdict_reason": verdict_result.get("reason"),
    }

    score_record = AttributionScore(
        drift_run_id=drift_run_id,
        scoring_version=scoring_version,
        cpa_score=Decimal(str(round(cpa_score_val, 3))),
        dark_vessel_score=Decimal(str(round(dark_score_val, 3))),
        loitering_score=Decimal(str(round(loiter_score_val, 3))),
        capacity_multiplier=Decimal(str(cap_mult_val)),
        draft_change_score=Decimal(str(round(draft_score_val, 3))),
        permutation_p_value=Decimal(str(round(p_val, 5))),
        stability_index=Decimal(str(round(stab_val, 3))),
        total_score=Decimal(str(round(total_score_val, 2))),
        verdict=verdict_enum_val,
        explanation=explanation_payload,
    )

    try:
        async with session.begin_nested():
            session.add(score_record)
            await session.flush()
        return score_record.id
    except IntegrityError:
        stmt = select(AttributionScore.id).where(
            AttributionScore.drift_run_id == drift_run_id,
            AttributionScore.scoring_version == scoring_version,
        )
        res = await session.execute(stmt)
        existing_id = res.scalar_one()
        return existing_id


async def write_audit_log(
    session: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    action: str,
    after_data: Dict[str, Any],
) -> UUID:
    """Write an append-only cryptographic hash-chained audit record."""
    stmt = select(AuditLog.event_hash).order_by(AuditLog.occurred_at.desc()).limit(1)
    res = await session.execute(stmt)
    prev_hash_row = res.scalar_one_or_none()
    previous_hash = str(prev_hash_row).strip() if prev_hash_row else None

    payload_str = (previous_hash or "") + json.dumps(after_data, sort_keys=True, default=str)
    event_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    action_enum_val = AuditActionEnum(action) if isinstance(action, str) else action

    audit_entry = AuditLog(
        actor_type=ActorTypeEnum.system,
        actor_id="attribution_pipeline",
        action=action_enum_val,
        entity_type=entity_type,
        entity_id=entity_id,
        after_data=after_data,
        metadata_={},
        hash_chain_previous=previous_hash,
        event_hash=event_hash,
    )
    session.add(audit_entry)
    await session.flush()
    return audit_entry.id
