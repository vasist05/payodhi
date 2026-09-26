"""
Geospatial utilities for maritime calculations.
Includes Haversine great-circle distance (Earth curvature correction per 22.txt)
and coordinate bounding-box generators for Indian maritime zones.
"""

import math
from typing import Tuple, List, Dict

# Earth radius in kilometers
EARTH_RADIUS_KM = 6371.0

# Strategic Indian Maritime Operational Zones (NTRO / Indian Coast Guard focus)
INDIAN_AOIS: Dict[str, Dict[str, float]] = {
    "mumbai_high": {
        "name": "Mumbai High Offshore Oil Field & Approaches",
        "lat": 18.90,
        "lon": 72.10,
        "min_lat": 18.0,
        "max_lat": 20.5,
        "min_lon": 71.0,
        "max_lon": 73.5,
    },
    "gulf_of_kutch": {
        "name": "Gulf of Kutch / Kandla / Vadinar Crude Terminals",
        "lat": 22.50,
        "lon": 69.50,
        "min_lat": 21.5,
        "max_lat": 23.5,
        "min_lon": 68.0,
        "max_lon": 70.5,
    },
    "chennai_ennore": {
        "name": "Chennai & Kamarajar (Ennore) Port Corridor (2017 Incident Zone)",
        "lat": 13.25,
        "lon": 80.35,
        "min_lat": 12.5,
        "max_lat": 14.2,
        "min_lon": 80.0,
        "max_lon": 81.5,
    },
    "haldia_sundarbans": {
        "name": "Haldia Port & Hooghly River Channel (2018 Incident Zone)",
        "lat": 21.75,
        "lon": 88.05,
        "min_lat": 21.0,
        "max_lat": 22.6,
        "min_lon": 87.5,
        "max_lon": 89.2,
    },
}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two points on Earth using Haversine formula.
    Accounts for Earth curvature (essential for distances > 10 km, as detailed in 22.txt).

    Returns:
        Distance in kilometers.
    """
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def get_bounding_box(lat: float, lon: float, radius_km: float = 150.0) -> List[List[List[float]]]:
    """
    Constructs a bounding box [[[lat_min, lon_min], [lat_max, lon_max]]]
    centered at (lat, lon) with given search radius in kilometers (default 150 km for Indian EEZ/AOIs).
    Formatted for the AISStream.io subscription schema.
    """
    dlat = math.degrees(radius_km / EARTH_RADIUS_KM)
    # Cosine correction for longitude distortion away from equator
    cos_lat = math.cos(math.radians(lat))
    dlon = math.degrees(radius_km / (EARTH_RADIUS_KM * max(0.01, cos_lat)))

    return [[[lat - dlat, lon - dlon], [lat + dlat, lon + dlon]]]
