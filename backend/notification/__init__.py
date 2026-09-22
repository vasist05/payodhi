"""Phase 8 — Coast Guard Alert + Interception Fleet Availability.

Public API:
    dispatch_response  — orchestrate a Coast Guard alert (Commit 4)
    haversine_km       — great-circle distance (Commit 2)
    nearest_stations   — nearest-N station selection (Commit 2)
    vessels_near_origin— interception-capable vessels near a point (Commit 2)
"""

from backend.notification.geo_utils import (
    haversine_km,
    nearest_stations,
    vessels_near_origin,
)

__all__ = [
    "haversine_km",
    "nearest_stations",
    "vessels_near_origin",
]