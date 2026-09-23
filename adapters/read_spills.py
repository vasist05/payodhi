"""Read spills + scenes. Returns a normalized detection dict for Phase 3."""
import json
from datetime import datetime
from .db_config import MOCK_MODE, get_connection, get_mock_path


def read_spill(spill_id: str):
    """
    Returns:
        {
            spill_id, scene_id, detection_lon, detection_lat,
            polygon, area_km2, detection_time, is_oil, confidence, sar_source
        }
    """
    if MOCK_MODE:
        with open(get_mock_path("spills")) as f:
            spills = json.load(f)
        with open(get_mock_path("scenes")) as f:
            scenes = json.load(f)

        spill = next((s for s in spills if s["spill_id"] == spill_id), None)
        if not spill:
            raise ValueError(f"spill_id {spill_id} not found in mock")
        scene = next((sc for sc in scenes if sc["scene_id"] == spill["scene_id"]), None)

        return {
            "spill_id": spill["spill_id"],
            "scene_id": spill["scene_id"],
            "detection_lon": spill["centroid_lon"],
            "detection_lat": spill["centroid_lat"],
            "polygon": spill["polygon"],
            "area_km2": spill["area_km2"],
            "detection_time": datetime.fromisoformat(
                spill["detection_time"].replace("Z", "+00:00")
            ),
            "is_oil": True,
            "confidence": spill["confidence"],
            "sar_source": scene["sar_source"] if scene else "unknown",
        }

    # --- Real DB ---
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                sp.id::text                              AS spill_id,
                sp.scene_id::text                        AS scene_id,
                ST_X(ST_Centroid(sp.spill_polygon))      AS centroid_lon,
                ST_Y(ST_Centroid(sp.spill_polygon))      AS centroid_lat,
                ST_AsGeoJSON(sp.spill_polygon)           AS polygon_geojson,
                sp.area_sq_km                            AS area_km2,
                sp.detected_at                           AS detection_time,
                sp.confidence_score                      AS confidence,
                sc.source_provider                       AS sar_source
            FROM spills sp
            JOIN scenes sc ON sc.id = sp.scene_id
            WHERE sp.id = %s
            """,
            (spill_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"spill_id {spill_id} not found in DB")

        (sid, scene_id, c_lon, c_lat, poly_geojson,
         area, det_time, conf, sar_src) = row

        return {
            "spill_id": sid,
            "scene_id": scene_id,
            "detection_lon": float(c_lon),
            "detection_lat": float(c_lat),
            "polygon": poly_geojson,
            "area_km2": float(area),
            "detection_time": det_time,
            "is_oil": True,
            "confidence": float(conf),
            "sar_source": sar_src,
        }
    finally:
        conn.close()