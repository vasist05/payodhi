"""
Service for persisting Phase 4 AIS & SAR Target Correlations into PostgreSQL.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MatchStatusEnum, SarTarget, TargetCorrelation, Vessel


async def persist_phase4_correlations(
    session: AsyncSession,
    scene_id: UUID,
    phase4_result: Dict[str, Any],
    detected_at: Optional[datetime] = None,
    source: str = "phase4_ca_cfar"
) -> Dict[str, Any]:
    """
    Persists Phase 4 AIS correlation output into sar_targets and target_correlations tables.

    Args:
        session: Active async database session.
        scene_id: UUID of the parent Scene.
        phase4_result: Output dict returned by run_phase4_pipeline().
        detected_at: Satellite scene capture timestamp. Defaults to UTC now.
        source: Detector identifier (default: 'phase4_ca_cfar').

    Returns:
        Dict with saved targets and correlations counts and IDs.
    """
    if detected_at is None:
        detected_at = datetime.now(timezone.utc)

    correlated_ships = phase4_result.get("correlated_ships", [])
    created_targets: List[SarTarget] = []
    created_correlations: List[TargetCorrelation] = []

    for ship in correlated_ships:
        lat = float(ship["lat"])
        lon = float(ship["lon"])
        intensity_val = ship.get("intensity")
        intensity = Decimal(str(round(intensity_val, 2))) if intensity_val is not None else None

        confidence = Decimal("0.850")
        if "confidence" in ship:
            confidence = Decimal(str(min(max(float(ship["confidence"]), 0.0), 1.0)))

        point_wkt = f"POINT({lon:.6f} {lat:.6f})"
        sar_target = SarTarget(
            scene_id=scene_id,
            detected_at=detected_at,
            position=WKTElement(point_wkt, srid=4326),
            intensity=intensity,
            confidence=confidence,
            patch_uri=ship.get("patch_uri"),
            source=source,
        )
        session.add(sar_target)
        await session.flush()
        created_targets.append(sar_target)

        raw_status = ship.get("status", "DARK_VESSEL").upper()
        if raw_status == "MATCHED":
            match_status = MatchStatusEnum.matched
        elif raw_status == "BORDERLINE":
            match_status = MatchStatusEnum.borderline
        else:
            match_status = MatchStatusEnum.dark_vessel

        vessel_id = None
        matched_mmsi = ship.get("matched_mmsi")
        if not matched_mmsi and isinstance(ship.get("ais_target"), dict):
            matched_mmsi = ship["ais_target"].get("mmsi")

        if matched_mmsi and match_status in (MatchStatusEnum.matched, MatchStatusEnum.borderline):
            stmt = select(Vessel).where(Vessel.mmsi == str(matched_mmsi)).limit(1)
            vessel = await session.scalar(stmt)
            if vessel:
                vessel_id = vessel.id

        # If matched status requires a vessel_id, but none was found in DB:
        # Fall back to borderline so the constraint (match_status='matched' AND vessel_id IS NOT NULL) is preserved!
        if match_status == MatchStatusEnum.matched and vessel_id is None:
            match_status = MatchStatusEnum.borderline

        dist_km = ship.get("distance_km")
        haversine_m = Decimal(str(round(dist_km * 1000.0, 2))) if dist_km is not None else None

        anomaly_flags = ship.get("behavioral_anomaly") or {}
        if not isinstance(anomaly_flags, dict):
            anomaly_flags = {"raw_anomaly": anomaly_flags}

        correlation = TargetCorrelation(
            sar_target_id=sar_target.id,
            vessel_id=vessel_id,
            match_status=match_status,
            haversine_distance_m=haversine_m,
            anomaly_flags=anomaly_flags,
        )
        session.add(correlation)
        await session.flush()
        created_correlations.append(correlation)

    return {
        "saved_targets_count": len(created_targets),
        "saved_correlations_count": len(created_correlations),
        "sar_target_ids": [t.id for t in created_targets],
        "correlation_ids": [c.id for c in created_correlations],
    }
