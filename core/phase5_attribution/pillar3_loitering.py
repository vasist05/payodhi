"""Pillar 3: Loitering & Sudden Speed Drop (ΔV).

Analyzes vessel kinematic deceleration and operational loitering.
Pure function adhering to phase5Final.md rules:
- Speed drop > 50% AND speed < 5 knots for > 30 minutes.
- Only within 6 hours of SAR time.
- Exclude port polygons (if provided).
- Exclude fishing vessels (fishing vessels excluded from loitering penalty).
- Boost 20% if course/heading change > 60° while slow.
- Cap score at 0.40 (cannot be sole evidence / capped at 40%).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import pyproj

logger = logging.getLogger(__name__)

MAX_LOITERING_SCORE = 0.40
SLOW_SPEED_KNOTS = 5.0
MIN_LOITERING_MINUTES = 30.0
SAR_WINDOW_HOURS = 6.0
COURSE_CHANGE_BOOST_DEG = 60.0
COURSE_BOOST_FACTOR = 1.20
NM_TO_METERS = 1852.0


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
    raise TypeError(f"Unsupported timestamp type: {type(t).__name__}")


def _point_in_polygon(lat: float, lon: float, polygon: List[Any]) -> bool:
    """Standard ray-casting algorithm to test if (lat, lon) is inside a polygon."""
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        p1 = polygon[i]
        p2 = polygon[j]
        # Support dict {"lat": ..., "lon": ...} or tuple (lat, lon)
        lat1 = p1["lat"] if isinstance(p1, dict) else p1[0]
        lon1 = p1["lon"] if isinstance(p1, dict) else p1[1]
        lat2 = p2["lat"] if isinstance(p2, dict) else p2[0]
        lon2 = p2["lon"] if isinstance(p2, dict) else p2[1]

        if ((lat1 > lat) != (lat2 > lat)) and (
            lon < (lon2 - lon1) * (lat - lat1) / ((lat2 - lat1) + 1e-12) + lon1
        ):
            inside = not inside
        j = i
    return inside


def _angle_difference(a1: float, a2: float) -> float:
    """Calculate minimal angular difference in degrees [0, 180]."""
    diff = abs(a1 - a2) % 360.0
    return 360.0 - diff if diff > 180.0 else diff


def detect_loitering(
    vessel_track: Optional[List[Dict[str, Any]]],
    sar_time: Union[datetime, str, float],
    port_polygons: Optional[List[List[Any]]] = None,
    vessel_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Detect operational loitering and sudden speed drops.

    Args:
        vessel_track: List of AIS track points {lat, lon, time, speed?, course?}.
        sar_time: SAR scene acquisition timestamp.
        port_polygons: Optional list of port/anchorage polygons to exclude.
        vessel_type: Optional vessel type (e.g. 'fishing', 'cargo').

    Returns:
        dict:
            loitering_score (float): Score capped at 0.40.
            events (list): Detected loitering events.
            reason (str): Explanatory reason and edge case notes.
    """
    if not vessel_track or len(vessel_track) < 2:
        return {
            "loitering_score": 0.0,
            "events": [],
            "reason": "INSUFFICIENT_DATA",
        }

    # Rule: Exclude fishing vessels from loitering penalty
    norm_type = (vessel_type or "").strip().lower()
    if not norm_type and vessel_track and "vessel_type" in vessel_track[0]:
        norm_type = str(vessel_track[0]["vessel_type"]).strip().lower()

    if norm_type == "fishing":
        logger.info("Fishing vessel detected. Excluded from loitering penalty.")
        return {
            "loitering_score": 0.0,
            "events": [],
            "reason": "fishing_vessel_excluded_from_loitering",
        }

    parsed_sar_time = _parse_timestamp(sar_time)
    window_start = parsed_sar_time - timedelta(hours=SAR_WINDOW_HOURS)
    window_end = parsed_sar_time + timedelta(hours=SAR_WINDOW_HOURS)

    # Parse and sort track by timestamp
    geod = pyproj.Geod(ellps="WGS84")
    parsed_points = []
    for p in vessel_track:
        lat = p.get("lat") if "lat" in p else p.get("latitude")
        lon = p.get("lon") if "lon" in p else p.get("lng", p.get("longitude"))
        t_val = p.get("time") if "time" in p else p.get("timestamp")
        sog = p.get("speed") if "speed" in p else p.get("sog")
        cog = p.get("course") if "course" in p else p.get("cog", p.get("heading"))
        parsed_points.append({
            "lat": float(lat),
            "lon": float(lon),
            "time": _parse_timestamp(t_val),
            "speed": float(sog) if sog is not None else None,
            "course": float(cog) if cog is not None else None,
        })

    parsed_points.sort(key=lambda x: x["time"])

    # Compute speeds and headings between points if missing
    for i in range(len(parsed_points)):
        if parsed_points[i]["speed"] is None:
            if i < len(parsed_points) - 1:
                p1, p2 = parsed_points[i], parsed_points[i + 1]
                dt_sec = (p2["time"] - p1["time"]).total_seconds()
                if dt_sec > 0:
                    az, _, dist_m = geod.inv(p1["lon"], p1["lat"], p2["lon"], p2["lat"])
                    calc_speed = (dist_m / NM_TO_METERS) / (dt_sec / 3600.0)
                    parsed_points[i]["speed"] = calc_speed
                    if parsed_points[i]["course"] is None:
                        parsed_points[i]["course"] = az % 360.0
                else:
                    parsed_points[i]["speed"] = 0.0
            elif i > 0:
                parsed_points[i]["speed"] = parsed_points[i - 1]["speed"]
                parsed_points[i]["course"] = parsed_points[i - 1]["course"]
            else:
                parsed_points[i]["speed"] = 0.0

    # Scan for loitering episodes
    # Criterion: Initial cruising speed drops by >50%, then stays <5 knots for >30 minutes
    events: List[Dict[str, Any]] = []
    reasons: List[str] = []

    i = 0
    n = len(parsed_points)
    while i < n - 1:
        pt = parsed_points[i]

        # Filter: Must be within 6 hours of SAR time
        if not (window_start <= pt["time"] <= window_end):
            i += 1
            continue

        # Check port exclusion
        if port_polygons:
            in_port = any(_point_in_polygon(pt["lat"], pt["lon"], poly) for poly in port_polygons)
            if in_port:
                i += 1
                continue

        # Look for slow sequence starting here
        if pt["speed"] < SLOW_SPEED_KNOTS:
            slow_start = pt["time"]
            slow_points = [pt]
            k = i + 1
            while k < n and parsed_points[k]["speed"] < SLOW_SPEED_KNOTS:
                slow_points.append(parsed_points[k])
                k += 1

            duration_min = (slow_points[-1]["time"] - slow_start).total_seconds() / 60.0

            # Must last > 30 minutes
            if duration_min >= MIN_LOITERING_MINUTES:
                # Check preceding cruise speed for >50% drop
                # Look back up to 60 mins before slow_start
                cruise_speeds = [
                    p["speed"] for p in parsed_points[:i]
                    if (slow_start - p["time"]).total_seconds() <= 3600.0 and p["speed"] is not None
                ]
                prev_speed = max(cruise_speeds) if cruise_speeds else None

                speed_drop_ratio = 0.0
                if prev_speed is not None and prev_speed > 0:
                    avg_slow_speed = sum(p["speed"] for p in slow_points) / len(slow_points)
                    speed_drop_ratio = (prev_speed - avg_slow_speed) / prev_speed

                # Qualifies if speed drop > 50% or cruising was >= 10 knots
                if speed_drop_ratio >= 0.50 or (prev_speed is not None and prev_speed >= 10.0):
                    # Check for course change > 60° while slow
                    courses = [p["course"] for p in slow_points if p["course"] is not None]
                    max_course_change = 0.0
                    if len(courses) >= 2:
                        for c1_idx in range(len(courses)):
                            for c2_idx in range(c1_idx + 1, len(courses)):
                                diff = _angle_difference(courses[c1_idx], courses[c2_idx])
                                if diff > max_course_change:
                                    max_course_change = diff

                    # Calculate base score based on duration and drop
                    base_score = 0.30
                    if duration_min >= 60.0:
                        base_score = 0.35

                    boost_applied = False
                    if max_course_change >= COURSE_CHANGE_BOOST_DEG:
                        base_score *= COURSE_BOOST_FACTOR
                        boost_applied = True

                    final_event_score = min(MAX_LOITERING_SCORE, base_score)

                    event_info = {
                        "start_time": slow_start,
                        "end_time": slow_points[-1]["time"],
                        "duration_minutes": round(duration_min, 1),
                        "initial_speed_knots": round(prev_speed, 1) if prev_speed else None,
                        "min_speed_knots": round(min(p["speed"] for p in slow_points), 1),
                        "max_course_change_deg": round(max_course_change, 1),
                        "course_boost": boost_applied,
                        "score": round(final_event_score, 3),
                    }
                    events.append(event_info)
                    reasons.append(
                        f"loitering_detected ({duration_min:.0f}m at <5kn, drop={speed_drop_ratio:.0%}"
                        + (", course_boost_applied" if boost_applied else "") + ")"
                    )

            i = k
        else:
            i += 1

    if not events:
        return {
            "loitering_score": 0.0,
            "events": [],
            "reason": "no_qualifying_loitering_events",
        }

    # Cap final overall score at MAX_LOITERING_SCORE (0.40)
    final_score = min(MAX_LOITERING_SCORE, max(e["score"] for e in events))

    return {
        "loitering_score": round(final_score, 3),
        "events": events,
        "reason": "; ".join(reasons),
    }
