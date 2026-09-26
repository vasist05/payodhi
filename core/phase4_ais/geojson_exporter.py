"""
GeoJSON Serializer for Phase 4 AIS & Dark Vessel Output.
Generates standard RFC 7946 FeatureCollections for frontend vector map layers (MapLibre / Leaflet).
Supports vessel position markers, historical track LineStrings, and dark vessel alerts.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Any


def to_geojson(
    correlations: Optional[List[Dict]] = None,
    dark_vessels: Optional[List[Dict]] = None,
    all_ais_vessels: Optional[List[Dict]] = None,
    spill_lat: float = 0.0,
    spill_lon: float = 0.0,
    correlated: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Constructs an RFC 7946 FeatureCollection from correlation outputs.
    Accepts either separate (correlations, dark_vessels, all_ais_vessels) or single correlated list.
    """
    features = []

    # 1. Spill Origin Point Feature
    features.append({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [spill_lon, spill_lat]
        },
        "properties": {
            "entity_type": "spill_origin",
            "status": "SPILL",
            "name": "Reported Oil Spill Origin",
            "description": "Centroid of detected oil slick from SAR analysis",
            "marker_color": "#FF3B30"
        }
    })

    # Normalize input into a unified vessel list
    ships_to_render = []

    if correlated is not None:
        ships_to_render.extend(correlated)

    if correlations is not None:
        for match in correlations:
            if "radar_target" in match and "ais_target" in match:
                radar = match["radar_target"]
                ais = match["ais_target"]
                ships_to_render.append({
                    "sar_id": radar.get("sar_id", radar.get("target_id", "SAR")),
                    "status": "MATCHED",
                    "matched_vessel": ais.get("name"),
                    "matched_mmsi": ais.get("mmsi"),
                    "imo": ais.get("imo"),
                    "flag": ais.get("flag", "Unknown"),
                    "dwt": ais.get("dwt"),
                    "vessel_type": ais.get("vessel_type", "Vessel"),
                    "speed_knots": ais.get("speed_knots", 0.0),
                    "heading": ais.get("heading", 0),
                    "distance_km": match.get("distance_km", 0.0),
                    "lat": ais.get("lat", radar.get("lat")),
                    "lon": ais.get("lon", radar.get("lon")),
                    "track": ais.get("track", []),
                    "behavioral_anomaly": match.get("behavioral_anomaly", {})
                })
            else:
                ships_to_render.append(match)

    if dark_vessels is not None:
        for dark in dark_vessels:
            sid = dark.get("sar_id", dark.get("target_id", "DARK"))
            ships_to_render.append({
                "sar_id": sid,
                "status": "DARK_VESSEL",
                "matched_vessel": None,
                "matched_mmsi": None,
                "imo": None,
                "flag": None,
                "dwt": None,
                "vessel_type": "Unidentified Radar Contact",
                "speed_knots": None,
                "heading": None,
                "distance_km": None,
                "lat": dark.get("lat", 0.0),
                "lon": dark.get("lon", 0.0),
                "track": [],
                "behavioral_anomaly": {
                    "anomaly_score": 90.0,
                    "flags": ["AIS_TRANSPONDER_INACTIVE"],
                    "gaps_detected": []
                }
            })

    # 2. Vessel Contact Points & Track Lines
    for ship in ships_to_render:
        is_dark = (ship.get("status") == "DARK_VESSEL")
        color = "#FF9500" if is_dark else "#34C759"
        track = ship.get("track", [])
        sid = ship.get("sar_id", "SAR")

        # Point Feature for Vessel Position
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [ship.get("lon", 0.0), ship.get("lat", 0.0)]
            },
            "properties": {
                "entity_type": "vessel_contact",
                "sar_id": sid,
                "status": ship.get("status", "MATCHED"),
                "name": ship.get("matched_vessel") or f"Dark Vessel (SAR #{sid})",
                "mmsi": ship.get("matched_mmsi"),
                "imo": ship.get("imo"),
                "flag": ship.get("flag"),
                "dwt": ship.get("dwt"),
                "vessel_type": ship.get("vessel_type"),
                "speed_knots": ship.get("speed_knots"),
                "heading": ship.get("heading"),
                "distance_to_sar_km": ship.get("distance_km"),
                "anomaly_score": ship.get("behavioral_anomaly", {}).get("anomaly_score", 0.0),
                "anomaly_flags": ship.get("behavioral_anomaly", {}).get("flags", []),
                "marker_color": color
            }
        })

        # LineString Feature for Vessel History Track
        if len(track) >= 2:
            coordinates = [[pt["lon"], pt["lat"]] for pt in track if "lat" in pt and "lon" in pt]
            if len(coordinates) >= 2:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coordinates
                    },
                    "properties": {
                        "entity_type": "vessel_track",
                        "vessel_name": ship.get("matched_vessel") or f"Vessel #{sid}",
                        "mmsi": ship.get("matched_mmsi"),
                        "num_waypoints": len(track),
                        "line_color": color,
                        "line_width": 2
                    }
                })

    return {
        "type": "FeatureCollection",
        "features": features
    }


def save_geojson(
    correlated: List[Dict],
    spill_lat: float,
    spill_lon: float,
    output_file: str = "core/phase4_ais/phase4_output.geojson"
) -> Dict:
    """
    Saves correlated vessels, track histories, and incident origin into GeoJSON format.
    """
    geojson_data = to_geojson(correlated=correlated, spill_lat=spill_lat, spill_lon=spill_lon)

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, indent=2)

    print(f"   [GEOJSON] Exported {len(geojson_data['features'])} vector features -> {output_file}")
    return geojson_data
