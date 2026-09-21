"""Pillar 1: Nautical Kinematic Intercept (CPA & TCPA).

Calculates Closest Point of Approach (CPA) and Time to Closest Point of
Approach (TCPA) between a vessel's historical AIS track and a forward-simulated
drift trajectory (e.g. from drift_runs table).

Strict Requirements & Edge Case Handling:
- Geodesic distance: pyproj.Geod (WGS-84 ellipsoid), strictly non-Euclidean.
- Timestamps: Converted to UTC.
- Duplicate timestamps: Deduplicated, preserving the last observation.
- Track interpolation: Linear/spline interpolation across the time grid so points
  are accurately time-aligned.
- Edge cases:
  * Vessel track < 2 points: log warning, cpa_score = 0.0
  * Drift trajectory empty: log error, cpa_score = 0.0
  * All vessel points identical (stationary/invalid): log warning, cpa_score = 0.0
  * Time alignment gap > 30 minutes: flag LOW_CONFIDENCE, halve cpa_score
  * TCPA sign: positive if CPA is in future relative to reference_time, negative if past
"""

from __future__ import annotations

import bisect
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import pyproj

logger = logging.getLogger(__name__)


def _parse_timestamp(t: Any) -> datetime:
    """Parse various timestamp representations into UTC datetime."""
    if t is None:
        raise ValueError("Timestamp cannot be None")
    if isinstance(t, datetime):
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc)
    if isinstance(t, (int, float)):
        return datetime.fromtimestamp(t, tz=timezone.utc)
    if isinstance(t, str):
        # Support ISO 8601 strings with Z or offset
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raise TypeError(f"Unsupported timestamp type: {type(t).__name__} ({t})")


def _extract_coord_point(p: Dict[str, Any]) -> Tuple[float, float, datetime]:
    """Extract (lat, lon, dt) from dict with varying key styles."""
    lat = p.get("lat") if "lat" in p else p.get("latitude")
    lon = p.get("lon") if "lon" in p else p.get("lng", p.get("longitude"))
    time_val = p.get("time") if "time" in p else p.get("timestamp")

    if lat is None or lon is None or time_val is None:
        raise ValueError(
            f"Point must contain lat/latitude, lon/lng/longitude, and time/timestamp. Got: {p}"
        )

    return float(lat), float(lon), _parse_timestamp(time_val)


def _deduplicate_and_sort_track(
    points: List[Tuple[float, float, datetime]]
) -> List[Tuple[float, float, datetime]]:
    """Deduplicate timestamps keeping the last observation, then sort by timestamp."""
    time_map: Dict[datetime, Tuple[float, float]] = {}
    for lat, lon, dt in points:
        time_map[dt] = (lat, lon)
    sorted_dts = sorted(time_map.keys())
    return [(time_map[dt][0], time_map[dt][1], dt) for dt in sorted_dts]


def _interpolate_position(
    sorted_track: List[Tuple[float, float, datetime]],
    target_dt: datetime,
) -> Tuple[float, float]:
    """Linearly interpolate lat/lon for target_dt within track bounds."""
    timestamps = [pt[2] for pt in sorted_track]

    # Exact match check
    idx = bisect.bisect_left(timestamps, target_dt)
    if idx < len(timestamps) and timestamps[idx] == target_dt:
        return sorted_track[idx][0], sorted_track[idx][1]

    if idx == 0 or idx >= len(timestamps):
        raise ValueError("Target timestamp is out of track bounds for interpolation.")

    t0, t1 = timestamps[idx - 1], timestamps[idx]
    lat0, lon0 = sorted_track[idx - 1][0], sorted_track[idx - 1][1]
    lat1, lon1 = sorted_track[idx][0], sorted_track[idx][1]

    total_secs = (t1 - t0).total_seconds()
    if total_secs <= 0:
        return lat0, lon0

    fraction = (target_dt - t0).total_seconds() / total_secs
    interp_lat = lat0 + fraction * (lat1 - lat0)
    interp_lon = lon0 + fraction * (lon1 - lon0)
    return interp_lat, interp_lon


def calculate_cpa(
    vessel_track: Optional[List[Dict[str, Any]]],
    drift_trajectory: Optional[List[Dict[str, Any]]],
    reference_time: Optional[Union[datetime, str, float]] = None,
    interpolate_missing: bool = True,
    max_alignment_gap_seconds: float = 1800.0,  # 30 minutes
) -> Dict[str, Any]:
    """Calculate Closest Point of Approach (CPA) and TCPA.

    Args:
        vessel_track: List of dicts with {lat, lon, time}.
        drift_trajectory: List of dicts with {lat, lon, time}.
        reference_time: Optional reference timestamp (e.g. SAR scene time or track start).
            TCPA is positive if CPA occurs in the future relative to reference_time,
            and negative if CPA occurred in the past. Defaults to vessel track start.
        interpolate_missing: Whether to resample/interpolate unaligned timestamps.
        max_alignment_gap_seconds: Maximum time gap (default 1800s / 30 min) before
            flagging LOW_CONFIDENCE and penalizing score.

    Returns:
        dict:
            min_distance_m (float or None): Geodesic CPA distance in meters.
            cpa_timestamp (datetime or None): UTC timestamp of CPA.
            tcpa_seconds (float or None): Signed seconds from reference_time to CPA.
            cpa_score (float): Normalized score [0.0 - 1.0] where 1.0 is direct intercept.
            vessel_point (dict or None): Vessel position at CPA {"lat": ..., "lon": ...}.
            drift_point (dict or None): Drift position at CPA {"lat": ..., "lon": ...}.
            low_confidence (bool): True if alignment gap exceeded threshold.
            explanation (str): Human/court-readable explanation of calculations and flags.
    """
    # Edge case 1: Drift trajectory empty
    if not drift_trajectory:
        logger.error("Drift trajectory is empty or None.")
        return {
            "min_distance_m": None,
            "cpa_timestamp": None,
            "tcpa_seconds": None,
            "cpa_score": 0.0,
            "vessel_point": None,
            "drift_point": None,
            "low_confidence": True,
            "explanation": "Drift trajectory is empty or missing.",
        }

    # Edge case 2: Vessel track has < 2 points
    if not vessel_track or len(vessel_track) < 2:
        logger.warning(
            "Vessel track has %d points (requires at least 2 points).",
            len(vessel_track) if vessel_track else 0,
        )
        return {
            "min_distance_m": None,
            "cpa_timestamp": None,
            "tcpa_seconds": None,
            "cpa_score": 0.0,
            "vessel_point": None,
            "drift_point": None,
            "low_confidence": True,
            "explanation": "Vessel track has insufficient points (< 2).",
        }

    # Extract, parse, deduplicate, and sort tracks
    v_parsed = [_extract_coord_point(p) for p in vessel_track]
    d_parsed = [_extract_coord_point(p) for p in drift_trajectory]

    v_points = _deduplicate_and_sort_track(v_parsed)
    d_points = _deduplicate_and_sort_track(d_parsed)

    # Edge case 3: All track points identical (stationary / invalid coordinates)
    first_pt = (v_points[0][0], v_points[0][1])
    if all((pt[0], pt[1]) == first_pt for pt in v_points):
        logger.warning("All vessel track points are identical; vessel was stationary or sensor jammed.")
        # Proceed with CPA calculation against stationary position, but flag explanation

    ref_dt = _parse_timestamp(reference_time) if reference_time is not None else v_points[0][2]

    # Geodesic calculator using WGS-84 ellipsoid
    geod = pyproj.Geod(ellps="WGS84")

    # Determine overlapping temporal window
    v_start, v_end = v_points[0][2], v_points[-1][2]
    d_start, d_end = d_points[0][2], d_points[-1][2]

    overlap_start = max(v_start, d_start)
    overlap_end = min(v_end, d_end)

    if overlap_start > overlap_end:
        logger.warning(
            "No temporal overlap between vessel track [%s, %s] and drift [%s, %s].",
            v_start.isoformat(),
            v_end.isoformat(),
            d_start.isoformat(),
            d_end.isoformat(),
        )
        return {
            "min_distance_m": None,
            "cpa_timestamp": None,
            "tcpa_seconds": None,
            "cpa_score": 0.0,
            "vessel_point": None,
            "drift_point": None,
            "low_confidence": True,
            "explanation": "No temporal overlap between vessel AIS and drift simulation.",
        }

    v_dict = {pt[2]: (pt[0], pt[1]) for pt in v_points}
    d_dict = {pt[2]: (pt[0], pt[1]) for pt in d_points}

    if interpolate_missing:
        all_timestamps = sorted(
            {pt[2] for pt in v_points if overlap_start <= pt[2] <= overlap_end}
            | {pt[2] for pt in d_points if overlap_start <= pt[2] <= overlap_end}
        )
    else:
        all_timestamps = sorted(set(v_dict.keys()) & set(d_dict.keys()))

    if not all_timestamps:
        return {
            "min_distance_m": None,
            "cpa_timestamp": None,
            "tcpa_seconds": None,
            "cpa_score": 0.0,
            "vessel_point": None,
            "drift_point": None,
            "low_confidence": True,
            "explanation": "No common or interpolatable timestamps in overlapping window.",
        }

    # Check for gaps > max_alignment_gap_seconds (30 min)
    max_gap_found = 0.0
    for i in range(1, len(all_timestamps)):
        gap_sec = (all_timestamps[i] - all_timestamps[i - 1]).total_seconds()
        if gap_sec > max_gap_found:
            max_gap_found = gap_sec

    low_confidence = max_gap_found > max_alignment_gap_seconds
    if low_confidence:
        logger.warning(
            "Time alignment gap of %.1f seconds exceeds threshold of %.1f seconds. Flagging LOW_CONFIDENCE.",
            max_gap_found,
            max_alignment_gap_seconds,
        )

    min_distance_m: Optional[float] = None
    cpa_timestamp: Optional[datetime] = None
    best_v_coord: Optional[Tuple[float, float]] = None
    best_d_coord: Optional[Tuple[float, float]] = None

    for dt in all_timestamps:
        # Get vessel position
        if dt in v_dict:
            v_lat, v_lon = v_dict[dt]
        else:
            v_lat, v_lon = _interpolate_position(v_points, dt)

        # Get drift position
        if dt in d_dict:
            d_lat, d_lon = d_dict[dt]
        else:
            d_lat, d_lon = _interpolate_position(d_points, dt)

        # Geodesic inverse distance on WGS-84 (handles Date Line automatically)
        _, _, distance_m = geod.inv(v_lon, v_lat, d_lon, d_lat)

        if min_distance_m is None or distance_m < min_distance_m:
            min_distance_m = distance_m
            cpa_timestamp = dt
            best_v_coord = (v_lat, v_lon)
            best_d_coord = (d_lat, d_lon)

    tcpa_seconds = (cpa_timestamp - ref_dt).total_seconds() if cpa_timestamp else None

    # Calculate normalized CPA score [0.0 - 1.0]
    # Standard maritime intercept decay: 1.0 at 0m, decaying to 0.0 at 10,000m (10km)
    if min_distance_m is not None:
        if min_distance_m <= 100.0:
            raw_cpa_score = 1.0
        elif min_distance_m >= 10000.0:
            raw_cpa_score = 0.0
        else:
            raw_cpa_score = max(0.0, 1.0 - (min_distance_m - 100.0) / 9900.0)
    else:
        raw_cpa_score = 0.0

    # If all points identical, set score = 0.0 per edge case spec
    if all((pt[0], pt[1]) == first_pt for pt in v_points):
        raw_cpa_score = 0.0

    # If alignment gap > 30 min, halve score per edge case spec
    final_cpa_score = raw_cpa_score * 0.5 if low_confidence else raw_cpa_score

    explanation = (
        f"CPA of {min_distance_m:.1f}m at {cpa_timestamp.isoformat()} UTC (TCPA: {tcpa_seconds:.1f}s). "
        f"Score: {final_cpa_score:.3f}"
        + (" [LOW_CONFIDENCE: alignment gap > 30m]" if low_confidence else "")
    )

    return {
        "min_distance_m": round(min_distance_m, 3) if min_distance_m is not None else None,
        "cpa_timestamp": cpa_timestamp,
        "tcpa_seconds": tcpa_seconds,
        "cpa_score": round(final_cpa_score, 4),
        "vessel_point": {"lat": best_v_coord[0], "lon": best_v_coord[1]} if best_v_coord else None,
        "drift_point": {"lat": best_d_coord[0], "lon": best_d_coord[1]} if best_d_coord else None,
        "low_confidence": low_confidence,
        "explanation": explanation,
    }
