"""
Correlation, Time Alignment & AIS Gap Detection Engine.
Performs:
1. AIS track blackout & gap detection (outages > 30 minutes).
2. SAR-AIS temporal alignment (interpolating vessel location at exact SAR pass time).
3. Associative matching between radar contacts and transponders via Haversine distance.
4. Multi-factor behavioral anomaly scoring (speed drops, transponder blackouts, cargo risk).
"""

import datetime
from typing import List, Dict, Tuple, Optional, Any, Union
from .geo_utils import haversine


class InterpolatedPosition(dict):
    """
    Position dict that supports both key access (pos['lat'])
    and tuple unpacking: lat, lon = pos.
    """
    def __iter__(self):
        yield self.get("lat")
        yield self.get("lon")


class AnomalyResult(dict):
    """
    Anomaly dict that supports key access (res['anomaly_score'])
    and tuple unpacking: score, factors = res.
    """
    def __iter__(self):
        yield self.get("anomaly_score", 0.0)
        yield self.get("flags", [])



def parse_iso_time(ts: str) -> datetime.datetime:
    """Parses standard ISO 8601 UTC timestamp."""
    clean = ts.replace("Z", "+00:00")
    return datetime.datetime.fromisoformat(clean)


def detect_ais_gaps(track: List[Dict], max_gap_seconds: int = 1800) -> List[Dict]:
    """
    Detects gaps in a vessel's chronological AIS track where the transponder
    stopped broadcasting for longer than `max_gap_seconds` (default: 30 minutes).

    Returns:
        List of identified gap intervals with start/end times and jump distance.
    """
    if not track or len(track) < 2:
        return []

    sorted_track = sorted(track, key=lambda p: parse_iso_time(p["timestamp"]))
    gaps = []

    for i in range(1, len(sorted_track)):
        t_prev = parse_iso_time(sorted_track[i - 1]["timestamp"])
        t_curr = parse_iso_time(sorted_track[i]["timestamp"])
        dt_seconds = (t_curr - t_prev).total_seconds()

        if dt_seconds > max_gap_seconds:
            jump_dist = haversine(
                sorted_track[i - 1]["lat"], sorted_track[i - 1]["lon"],
                sorted_track[i]["lat"], sorted_track[i]["lon"]
            )
            duration_min = round(dt_seconds / 60.0, 1)
            gap_info = {
                "gap_start": sorted_track[i - 1]["timestamp"],
                "gap_end": sorted_track[i]["timestamp"],
                "duration_minutes": duration_min,
                "gap_duration_minutes": duration_min,
                "start_coord": [sorted_track[i - 1]["lat"], sorted_track[i - 1]["lon"]],
                "end_coord": [sorted_track[i]["lat"], sorted_track[i]["lon"]],
                "distance_jump_km": round(jump_dist, 2)
            }
            gaps.append(gap_info)

    return gaps


def interpolate_position_at_time(track: List[Dict], target_time_iso: str) -> Optional[InterpolatedPosition]:
    """
    Interpolates a vessel's coordinates at an exact target timestamp (e.g. SAR satellite pass).
    Returns an InterpolatedPosition dict which can also be unpacked as (lat, lon).
    """
    if not track:
        return None

    if len(track) == 1:
        pt = track[0]
        return InterpolatedPosition({
            "lat": pt["lat"],
            "lon": pt["lon"],
            "speed_knots": pt.get("speed_knots", 0.0),
            "heading": pt.get("heading", 0)
        })

    sorted_track = sorted(track, key=lambda p: parse_iso_time(p["timestamp"]))
    target_dt = parse_iso_time(target_time_iso)

    # Before first recorded waypoint
    if target_dt <= parse_iso_time(sorted_track[0]["timestamp"]):
        pt = sorted_track[0]
        return InterpolatedPosition({
            "lat": pt["lat"],
            "lon": pt["lon"],
            "speed_knots": pt.get("speed_knots", 0.0),
            "heading": pt.get("heading", 0)
        })

    # After last recorded waypoint
    if target_dt >= parse_iso_time(sorted_track[-1]["timestamp"]):
        pt = sorted_track[-1]
        return InterpolatedPosition({
            "lat": pt["lat"],
            "lon": pt["lon"],
            "speed_knots": pt.get("speed_knots", 0.0),
            "heading": pt.get("heading", 0)
        })

    # Interpolate between flanking waypoints
    for i in range(1, len(sorted_track)):
        t_a = parse_iso_time(sorted_track[i - 1]["timestamp"])
        t_b = parse_iso_time(sorted_track[i]["timestamp"])

        if t_a <= target_dt <= t_b:
            total_span = (t_b - t_a).total_seconds()
            if total_span == 0:
                fraction = 0.0
            else:
                fraction = (target_dt - t_a).total_seconds() / total_span

            lat_a, lon_a = sorted_track[i - 1]["lat"], sorted_track[i - 1]["lon"]
            lat_b, lon_b = sorted_track[i]["lat"], sorted_track[i]["lon"]

            interp_lat = lat_a + fraction * (lat_b - lat_a)
            interp_lon = lon_a + fraction * (lon_b - lon_a)

            return InterpolatedPosition({
                "lat": round(interp_lat, 5),
                "lon": round(interp_lon, 5),
                "speed_knots": sorted_track[i - 1].get("speed_knots", 0.0),
                "heading": sorted_track[i - 1].get("heading", 0),
                "interpolated": True,
                "timestamp": target_time_iso
            })

    pt = sorted_track[-1]
    return InterpolatedPosition({
        "lat": pt["lat"],
        "lon": pt["lon"],
        "speed_knots": pt.get("speed_knots", 0.0),
        "heading": pt.get("heading", 0)
    })


def compute_behavioral_anomaly(
    vessel: Dict,
    spill_lat: Optional[float] = None,
    spill_lon: Optional[float] = None
) -> Dict:
    """
    Evaluates multi-factor behavioral anomalies based on:
    - Speed drop anomaly (vessels illegally discharging slow to 1-5.5 knots)
    - AIS transponder blackout gaps (> 30 min)
    - Vessel risk profile & cargo capacity
    """
    speed = vessel.get("speed_knots", 10.0)
    vessel_type = str(vessel.get("vessel_type", "")).lower()
    track = vessel.get("track", [])

    anomaly_flags = []
    anomaly_score = 0.0

    # 1. Speed drop anomaly in open navigation corridor
    if 1.0 < speed <= 5.5:
        anomaly_score += 35.0
        anomaly_flags.append("SLOW_TRANSIT_ANOMALY (Plausible discharge / loitering speed: 1.0-5.5 kts)")
    elif speed <= 1.0:
        anomaly_score += 15.0
        anomaly_flags.append("DRIFTING_OR_ANCHORED")

    # 2. AIS Gap / Blackout Detection
    gaps = detect_ais_gaps(track, max_gap_seconds=1800)
    if gaps:
        total_blackout_min = sum(g["duration_minutes"] for g in gaps)
        anomaly_score += 40.0
        anomaly_flags.append(f"TRANSPONDER_BLACKOUT_DETECTED ({len(gaps)} gaps, total: {total_blackout_min:.0f} min)")

    # 3. Vessel Type & Environmental Risk Weighting
    if "tanker" in vessel_type or "crude" in vessel_type or "oil" in vessel_type:
        anomaly_score += 30.0
        anomaly_flags.append("HIGH_RISK_CARGO_CATEGORY (Crude/Product Tanker)")
    elif "chemical" in vessel_type or "lpg" in vessel_type:
        anomaly_score += 25.0
        anomaly_flags.append("HAZARDOUS_LIQUID_CARRIER (Chemical/Gas Carrier)")
    elif "cargo" in vessel_type or "container" in vessel_type:
        anomaly_score += 10.0
        anomaly_flags.append("COMMERCIAL_CARGO_CATEGORY")

    return AnomalyResult({
        "anomaly_score": min(100.0, anomaly_score),
        "flags": anomaly_flags,
        "gaps_detected": gaps
    })


def correlate_sar_ais(
    sar_ships: Optional[List[Dict]] = None,
    ais_ships: Optional[List[Dict]] = None,
    radar_targets: Optional[List[Dict]] = None,
    ais_targets: Optional[List[Dict]] = None,
    match_threshold_km: float = 5.0,
    sar_acquisition_time: Optional[str] = None
) -> Tuple[List[Dict], List[Dict]]:
    """
    Correlates SAR ship detections with AIS vessels.
    Returns:
        (correlations_matched, dark_vessels)
    """
    radar_list = sar_ships if sar_ships is not None else (radar_targets if radar_targets is not None else [])
    ais_list = ais_ships if ais_ships is not None else (ais_targets if ais_targets is not None else [])

    print(f"\nCorrelating SAR Radar Contacts with AIS Fleet...")
    print(f"   Association Threshold: {match_threshold_km} km")
    if sar_acquisition_time:
        print(f"   Temporal Alignment Anchor: {sar_acquisition_time} (SAR Acquisition Pass)")

    # Compute time-aligned positions for each AIS ship
    aligned_fleet = []
    for s in ais_list:
        s_copy = dict(s)
        if sar_acquisition_time and s.get("track"):
            interp = interpolate_position_at_time(s["track"], sar_acquisition_time)
            if interp:
                s_copy["lat"] = interp["lat"]
                s_copy["lon"] = interp["lon"]
                s_copy["speed_knots"] = interp.get("speed_knots", s_copy.get("speed_knots"))
                s_copy["heading"] = interp.get("heading", s_copy.get("heading"))
        aligned_fleet.append(s_copy)

    matched = []
    dark_vessels = []

    for sar_ship in radar_list:
        sid = sar_ship.get("sar_id", sar_ship.get("target_id", "SAR-0"))
        tid = sar_ship.get("target_id", f"SAR-{sid}")
        best_match: Optional[Dict] = None
        min_distance = float("inf")

        for ais_ship in aligned_fleet:
            dist = haversine(
                sar_ship["lat"], sar_ship["lon"],
                ais_ship["lat"], ais_ship["lon"]
            )
            if dist < min_distance:
                min_distance = dist
                if dist <= match_threshold_km:
                    best_match = ais_ship

        if best_match:
            anomaly_info = compute_behavioral_anomaly(best_match)
            print(f"   [MATCHED] SAR Target #{sid} -> {best_match.get('name')} "
                  f"(dist: {min_distance:.2f} km, MMSI: {best_match.get('mmsi')})")

            match_record = {
                "sar_id": sid,
                "target_id": tid,
                "radar_target": sar_ship,
                "ais_target": best_match,
                "lat": sar_ship["lat"],
                "lon": sar_ship["lon"],
                "intensity": sar_ship.get("intensity", 1.0),
                "status": "MATCHED",
                "matched_vessel": best_match.get("name"),
                "matched_mmsi": best_match.get("mmsi"),
                "imo": best_match.get("imo"),
                "flag": best_match.get("flag", "Unknown"),
                "dwt": best_match.get("dwt"),
                "length": best_match.get("length"),
                "beam": best_match.get("beam"),
                "vessel_type": best_match.get("vessel_type", "Unknown"),
                "speed_knots": best_match.get("speed_knots", 0.0),
                "heading": best_match.get("heading", 0),
                "distance_km": round(min_distance, 2),
                "track": best_match.get("track", []),
                "behavioral_anomaly": anomaly_info
            }
            matched.append(match_record)
        else:
            print(f"   [ALERT]   SAR Target #{sid}: DARK VESSEL DETECTED "
                  f"(closest transponder: {min_distance:.2f} km)")

            dark_record = {
                "sar_id": sid,
                "target_id": tid,
                "is_dark": True,
                "radar_target": sar_ship,
                "lat": sar_ship["lat"],
                "lon": sar_ship["lon"],
                "intensity": sar_ship.get("intensity", 1.0),
                "status": "DARK_VESSEL",
                "matched_vessel": None,
                "matched_mmsi": None,
                "imo": None,
                "flag": None,
                "dwt": None,
                "length": None,
                "beam": None,
                "vessel_type": "Unidentified Radar Contact",
                "speed_knots": None,
                "heading": None,
                "distance_km": round(min_distance, 2) if min_distance != float("inf") else None,
                "track": [],
                "behavioral_anomaly": {
                    "anomaly_score": 90.0,
                    "flags": ["AIS_TRANSPONDER_INACTIVE (Unidentified radar target without AIS broadcast)"],
                    "gaps_detected": []
                }
            }
            dark_vessels.append(dark_record)

    return matched, dark_vessels
