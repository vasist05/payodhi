"""
backend/app/schemas/common.py

Spatial conversion helpers between GeoJSON dictionaries and WKT strings
for PostGIS interoperability.
"""

from __future__ import annotations

import json
from typing import Any


def geojson_to_wkt(geojson_dict: dict[str, Any]) -> str:
    """
    Convert a GeoJSON geometry dictionary (Polygon, MultiPolygon) to WKT format.
    Falls back to basic JSON-to-WKT reconstruction if shapely is not installed.
    """
    try:
        from shapely.geometry import shape
        geom = shape(geojson_dict)
        # PostGIS spills requires MultiPolygon; promote Polygon if needed
        if geom.geom_type == "Polygon":
            from shapely.geometry import MultiPolygon
            geom = MultiPolygon([geom])
        return geom.wkt
    except ImportError:
        # Fallback parser for standard Polygon/MultiPolygon coordinates
        gtype = geojson_dict.get("type", "Polygon")
        coords = geojson_dict.get("coordinates", [])
        if gtype == "Polygon":
            rings = []
            for ring in coords:
                pt_strs = [f"{pt[0]} {pt[1]}" for pt in ring]
                rings.append(f"({', '.join(pt_strs)})")
            return f"MULTIPOLYGON(({', '.join(rings)}))"
        elif gtype == "MultiPolygon":
            poly_strs = []
            for poly in coords:
                rings = []
                for ring in poly:
                    pt_strs = [f"{pt[0]} {pt[1]}" for pt in ring]
                    rings.append(f"({', '.join(pt_strs)})")
                poly_strs.append(f"({', '.join(rings)})")
            return f"MULTIPOLYGON({', '.join(poly_strs)})"
        raise ValueError(f"Unsupported geometry type: {gtype}")


def wkt_to_geojson(wkt_str: str) -> dict[str, Any]:
    """Convert a WKT string to a GeoJSON geometry dictionary."""
    try:
        from shapely import wkt
        from shapely.geometry import mapping
        geom = wkt.loads(wkt_str)
        return mapping(geom)
    except ImportError:
        # Basic representation
        return {"type": "MultiPolygon", "wkt": wkt_str}
