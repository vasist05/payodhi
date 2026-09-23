"""Read vessels + tracks. Returns candidate ship list for forward attribution."""
import json
from datetime import datetime
from .db_config import MOCK_MODE, get_connection, get_mock_path


CARGO_TO_OIL = {
    "crude_oil":   "GENERIC HEAVY CRUDE",
    "diesel":      "DIESEL",
    "fuel_oil":    "FUEL OIL NO. 6",
    "gasoline":    "GASOLINE",
    "unknown":     "GENERIC MEDIUM CRUDE",
}


def _oil_from_vessel_type(vessel_type: str) -> str:
    """Map vessel_type_enum -> an OpenOil-compatible oil type."""
    vt = (vessel_type or "").lower()
    if "crude" in vt:
        return "GENERIC HEAVY CRUDE"
    if "chemical" in vt:
        return "GENERIC MEDIUM CRUDE"
    if "cargo" in vt or "container" in vt:
        return "FUEL OIL NO. 6"
    if "fishing" in vt:
        return "DIESEL"
    return "GENERIC MEDIUM CRUDE"


def read_candidates(release_window_start, release_window_end):
    """
    Return candidate vessels whose AIS track lies inside the release window.
    Each dict: mmsi, vessel_name, vessel_type, declared_cargo, oil_type,
               lon, lat, release_time, vessel_id (UUID from DB).
    """
    if MOCK_MODE:
        with open(get_mock_path("vessels")) as f:
            vessels = json.load(f)
        with open(get_mock_path("tracks")) as f:
            tracks = json.load(f)

        out = []
        for v in vessels:
            for t in tracks:
                if t["mmsi"] != v["mmsi"]:
                    continue
                ts = datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00"))
                if release_window_start <= ts <= release_window_end:
                    cargo = v.get("declared_cargo", "unknown")
                    out.append({
                        "mmsi": v["mmsi"],
                        "vessel_name": v["vessel_name"],
                        "vessel_type": v["vessel_type"],
                        "declared_cargo": cargo,
                        "oil_type": CARGO_TO_OIL.get(cargo, "GENERIC MEDIUM CRUDE"),
                        "lon": t["lon"],
                        "lat": t["lat"],
                        "release_time": ts,
                        "vessel_id": None,
                    })
                    break
        return out

    # --- Real DB ---
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT ON (v.id)
                v.id::text                     AS vessel_id,
                v.mmsi,
                v.vessel_name,
                v.vessel_type::text            AS vessel_type,
                t.recorded_at                  AS release_time,
                ST_X(t.position)               AS lon,
                ST_Y(t.position)               AS lat
            FROM vessels v
            JOIN tracks t ON t.vessel_id = v.id
            WHERE t.recorded_at BETWEEN %s AND %s
            ORDER BY v.id, t.recorded_at
            """,
            (release_window_start, release_window_end),
        )

        out = []
        for vessel_id, mmsi, name, vtype, rec_at, lon, lat in cur.fetchall():
            out.append({
                "vessel_id": vessel_id,
                "mmsi": mmsi or "unknown",
                "vessel_name": name or "unknown",
                "vessel_type": vtype or "unknown",
                "declared_cargo": "unknown",
                "oil_type": _oil_from_vessel_type(vtype),
                "lon": float(lon),
                "lat": float(lat),
                "release_time": rec_at,
            })
        return out
    finally:
        conn.close()