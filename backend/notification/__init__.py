"""Phase 8 — Coast Guard Alert + Interception Fleet Availability.

Public API:
    dispatch_response   — orchestrate a Coast Guard alert
    haversine_km        — great-circle distance
    nearest_stations    — nearest-N station selection
    vessels_near_origin — interception-capable vessels near a point
    bus                 — asyncio pub/sub for WebSocket fan-out
"""

from backend.notification.event_bus import bus
from backend.notification.geo_utils import (
    haversine_km,
    nearest_stations,
    vessels_near_origin,
)
from backend.notification.response_engine import dispatch_response

__all__ = [
    "dispatch_response",
    "haversine_km",
    "nearest_stations",
    "vessels_near_origin",
    "bus",
]