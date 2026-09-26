"""Pillar 2: 'Dark Vessel' & AIS Gap Detection.

Detects deliberate transponder shutoffs and anomalous silence windows.
Pure function adhering to phase5Final.md master rules:
- Gap threshold: > 10 minutes (matching ais_gaps.gap_duration_min).
- Open ocean filter: only flag if > 5 nm from coast (or half-weighted if coastal departure).
- Proximity filter: only flag if gap center is within 50 nm of spill center.
- Duration > 24 hours: flag as PERMANENT_BLACKOUT (score = 0.0).
- Speed jumps > 30 knots: flag AIS_SPOOFING_SUSPECTED (score reduced by 50%).
- Multiple gaps: take max score, do not sum.
- Geodesic math: pyproj.Geod (WGS-84 ellipsoid).
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import pyproj

logger = logging.getLogger(__name__)

NM_TO_METERS = 1852.0
MAX_SPILL_DISTANCE_NM = 50.0
MIN_GAP_DURATION_MIN = 10.0
MAX_GAP_DURATION_HOURS = 24.0
SPOOFING_SPEED_KNOTS = 30.0
COASTAL_THRESHOLD_NM = 5.0


def _parse_timestamp(t: Any) -> datetime:
    if t is None:
        raise ValueError("Timestamp cannot be None")
    if isinstance(t, datetime):
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc)
    if isinstance(t, (int, float)):
        return datetime.fromtimestamp(t, tz=timezone.utc)
    if isinstance(t, str):
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raise TypeError(f"Unsupported timestamp type: {type(t).__name__} ({t})")


def _extract_coord_point(p: Dict[str, Any]) -> Tuple[float, float, datetime]:
    lat = p.get("lat") if "lat" in p else p.get("latitude")
    lon = p.get("lon") if "lon" in p else p.get("lng", p.get("longitude"))
    time_val = p.get("time") if "time" in p else p.get("timestamp")
    if lat is None or lon is None or time_val is None:
        raise ValueError(f"Invalid point: {p}")
    return float(lat), float(lon), _parse_timestamp(time_val)


def _extract_spill_coord(spill: Union[Dict[str, Any], Tuple[float, float], List[float]]) -> Tuple[float, float]:
    if isinstance(spill, (tuple, list)) and len(spill) >= 2:
        return float(spill[0]), float(spill[1])
    if isinstance(spill, dict):
        lat = spill.get("lat") if "lat" in spill else spill.get("latitude")
        lon = spill.get("lon") if "lon" in spill else spill.get("lng", spill.get("longitude"))
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    raise ValueError(f"Invalid spill center: {spill}")


def detect_dark_window(
    vessel_track: Optional[List[Dict[str, Any]]],
    spill_center: Union[Dict[str, Any], Tuple[float, float], List[float]],
    spill_time: Optional[Union[datetime, str, float]] = None,
    coastline_distance_nm: Optional[float] = None,
) -> Dict[str, Any]:
    """Detect deliberate AIS silence windows (dark vessels).

    Args:
        vessel_track: List of AIS points {lat, lon, time}.
        spill_center: Spill origin location {lat, lon} or (lat, lon).
        spill_time: Optional timestamp of the SAR spill detection.
        coastline_distance_nm: Distance from coast in nautical miles.

    Returns:
        dict:
            dark_vessel_score (float): Normalized score [0.0 - 1.0].
            gaps (list): List of detected gap details.
            reason (str): Explanatory reason and edge case flags.
    """
    if not vessel_track or len(vessel_track) < 2:
        logger.warning("No AIS data or insufficient points for region.")
        return {
            "dark_vessel_score": 0.0,
            "gaps": [],
            "reason": "INSUFFICIENT_EVIDENCE",
        }

    try:
        spill_lat, spill_lon = _extract_spill_coord(spill_center)
    except Exception as e:
        logger.error("Invalid spill center coordinates: %s", e)
        return {
            "dark_vessel_score": 0.0,
            "gaps": [],
            "reason": "INVALID_SPILL_CENTER",
        }

    parsed_spill_time = _parse_timestamp(spill_time) if spill_time is not None else None

    # Sort and deduplicate vessel track points
    parsed_points = [_extract_coord_point(p) for p in vessel_track]
    time_map: Dict[datetime, Tuple[float, float]] = {}
    for lat, lon, dt in parsed_points:
        time_map[dt] = (lat, lon)
    sorted_dts = sorted(time_map.keys())
    sorted_track = [(time_map[dt][0], time_map[dt][1], dt) for dt in sorted_dts]

    if len(sorted_track) < 2:
        return {
            "dark_vessel_score": 0.0,
            "gaps": [],
            "reason": "INSUFFICIENT_EVIDENCE",
        }

    geod = pyproj.Geod(ellps="WGS84")
    gaps: List[Dict[str, Any]] = []
    gap_scores: List[float] = []
    reason_notes: List[str] = []

    for i in range(len(sorted_track) - 1):
        p1 = sorted_track[i]
        p2 = sorted_track[i + 1]

        duration_sec = (p2[2] - p1[2]).total_seconds()
        if duration_sec <= 0:
            continue

        duration_min = duration_sec / 60.0

        # Edge case: Gap < 10 min -> Ignore
        if duration_min < MIN_GAP_DURATION_MIN:
            continue

        # Geodesic distance between endpoints
        _, _, distance_m = geod.inv(p1[1], p1[0], p2[1], p2[0])
        distance_nm = distance_m / NM_TO_METERS
        speed_knots = (distance_nm / (duration_sec / 3600.0)) if duration_sec > 0 else 0.0

        # Midpoint of gap
        mid_lat = (p1[0] + p2[0]) / 2.0
        mid_lon = (p1[1] + p2[1]) / 2.0

        # Distance from gap center to spill
        _, _, dist_to_spill_m = geod.inv(spill_lon, spill_lat, mid_lon, mid_lat)
        dist_to_spill_nm = dist_to_spill_m / NM_TO_METERS

        gap_info = {
            "gap_start": p1[2],
            "gap_end": p2[2],
            "gap_duration_min": round(duration_min, 1),
            "distance_to_spill_nm": round(dist_to_spill_nm, 2),
            "speed_knots": round(speed_knots, 2),
            "gap_center": {"lat": round(mid_lat, 5), "lon": round(mid_lon, 5)},
        }

        # Edge case: Gap > 24 hours -> PERMANENT_BLACKOUT, score = 0.0
        if duration_min > (MAX_GAP_DURATION_HOURS * 60.0):
            gap_info["flag"] = "PERMANENT_BLACKOUT"
            gap_info["score"] = 0.0
            gaps.append(gap_info)
            reason_notes.append("PERMANENT_BLACKOUT_gap_exceeds_24h")
            continue

        # Proximity check: Must be within 50 nm of spill center
        if dist_to_spill_nm > MAX_SPILL_DISTANCE_NM:
            gap_info["flag"] = "EXCLUDED_BEYOND_50NM"
            gap_info["score"] = 0.0
            gaps.append(gap_info)
            continue

        # Coastline check: Open ocean (> 5 nm from coast)
        # If coastline_distance_nm is provided and <= 5.0, half weight (legit port departure)
        coastal_factor = 1.0
        if coastline_distance_nm is not None and coastline_distance_nm <= COASTAL_THRESHOLD_NM:
            coastal_factor = 0.5
            gap_info["coastal_penalty"] = True
            reason_notes.append("coastal_departure_half_weight")

        # Base score from duration (10 min to 120 min) and proximity (0 nm to 50 nm)
        duration_factor = min(1.0, duration_min / 60.0)
        proximity_factor = max(0.0, 1.0 - (dist_to_spill_nm / MAX_SPILL_DISTANCE_NM))
        raw_score = duration_factor * proximity_factor * coastal_factor

        # Edge case: Speed jump > 30 knots -> AIS_SPOOFING_SUSPECTED (halve score)
        if speed_knots > SPOOFING_SPEED_KNOTS:
            raw_score *= 0.5
            gap_info["flag"] = "AIS_SPOOFING_SUSPECTED"
            reason_notes.append("AIS_SPOOFING_SUSPECTED_speed_jump")

        # Check temporal overlap with spill time if provided
        if parsed_spill_time is not None:
            if p1[2] <= parsed_spill_time <= p2[2]:
                gap_info["spill_overlap"] = True
                raw_score = min(1.0, raw_score * 1.2)  # 20% boost if spill occurs during gap

        gap_info["score"] = round(raw_score, 4)
        gaps.append(gap_info)
        gap_scores.append(raw_score)

    if not gap_scores:
        final_score = 0.0
        if not reason_notes:
            reason = "no_suspicious_gaps_detected"
        else:
            reason = "; ".join(set(reason_notes))
    else:
        # Multiple gaps for same vessel: Take max score, don't sum
        final_score = round(max(gap_scores), 4)
        notes_str = f" [{'; '.join(set(reason_notes))}]" if reason_notes else ""
        reason = f"dark_vessel_anomaly_detected (max_gap_score={final_score:.4f}){notes_str}"

    return {
        "dark_vessel_score": final_score,
        "gaps": gaps,
        "reason": reason,
    }


if __name__ == "__main__":
    import json

    print("=" * 70)
    print("PAYODHI — PILLAR 2: DARK VESSEL & AIS GAP DETECTION")
    print("=" * 70)

    spill_loc = {"lat": 18.0, "lon": 72.0}
    spill_timestamp = datetime(2026, 9, 21, 10, 30, 0, tzinfo=timezone.utc)
    vessel_trajectory = [
        {"lat": 17.95, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 10, 0, tzinfo=timezone.utc)},
        {"lat": 18.05, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 50, 0, tzinfo=timezone.utc)},
    ]

    print("\n[Scenario 1: Open-ocean transponder gap (40 min) overlapping spill]")
    res1 = detect_dark_window(
        vessel_track=vessel_trajectory,
        spill_center=spill_loc,
        spill_time=spill_timestamp,
        coastline_distance_nm=20.0,
    )
    print(f"Dark Vessel Score : {res1['dark_vessel_score']}")
    print(f"Reason            : {res1['reason']}")
    print("Gap Details:")
    print(json.dumps(res1["gaps"], indent=2, default=str))

    print("\n[Scenario 2: Coastal departure gap (<= 5 nm from coast, half weight)]")
    res2 = detect_dark_window(
        vessel_track=vessel_trajectory,
        spill_center=spill_loc,
        spill_time=spill_timestamp,
        coastline_distance_nm=3.0,
    )
    print(f"Dark Vessel Score : {res2['dark_vessel_score']}")
    print(f"Reason            : {res2['reason']}")

    print("\n[Scenario 3: Anomaly / AIS Spoofing speed jump (>30 knots)]")
    spoof_track = [
        {"lat": 18.0, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)},
        {"lat": 19.0, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 30, 0, tzinfo=timezone.utc)},
    ]
    res3 = detect_dark_window(
        vessel_track=spoof_track,
        spill_center=spill_loc,
    )
    print(f"Dark Vessel Score : {res3['dark_vessel_score']}")
    print(f"Reason            : {res3['reason']}")

    print("\n" + "=" * 70)
    print("Execution complete: Pillar 2 algorithm running successfully.")
    print("=" * 70)
