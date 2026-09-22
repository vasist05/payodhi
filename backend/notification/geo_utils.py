"""Geospatial helpers for Phase 8.

Haversine distance plus two proximity queries:
    - nearest_stations       : nearest-N Coast Guard stations to a point
    - vessels_near_origin    : interception-capable vessels within a radius

Design note on vessel shape:
    Phase 4 emits vessels with `position_lat` / `position_lon`.
    The Phase 8 fallback registry uses `lat` / `lon`.
    `vessels_near_origin` accepts BOTH so Phase 4 raw output works without a
    boundary adapter. Prefer `lat`/`lon` if present, fall back to
    `position_lat`/`position_lon`.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

EARTH_RADIUS_KM = 6371.0088

# Vessel types considered "interception capable". Matched case-insensitively
# as substrings against a vessel's `type` field. Anything not matching is
# excluded from the interception count — Phase 8 counts interceptors, not
# suspects (e.g. "Crude Oil Tanker" is intentionally rejected).
DEFAULT_INTERCEPTION_TYPES: tuple[str, ...] = (
    "Tug",
    "Towing",
    "Patrol Vessel",
    "Law Enforcement",
    "Oil Recovery",
    "Pollution Control",
    "SAR",
    "Naval Auxiliary",
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    # Clamp a to [0, 1] to guard against floating-point drift for antipodal points
    a = min(1.0, max(0.0, a))
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_stations(
    origin_lat: float,
    origin_lon: float,
    stations: Iterable[dict[str, Any]],
    max_results: int = 3,
    max_distance_km: float = 500.0,
) -> list[dict[str, Any]]:
    """Return the nearest `max_results` stations within `max_distance_km`.

    `response_radius_km` on each station is carried through as metadata but
    does NOT filter the search — it is a capability attribute used by the
    response engine for severity gating, not a search bound.

    Each returned station is a shallow copy with an added `distance_km`
    (rounded to 1 decimal). Sorted ascending by distance.
    """
    scored: list[dict[str, Any]] = []
    for s in stations:
        s_lat, s_lon = s.get("lat"), s.get("lon")
        if s_lat is None or s_lon is None:
            continue
        d = haversine_km(origin_lat, origin_lon, s_lat, s_lon)
        if d <= max_distance_km:
            scored.append({**s, "distance_km": round(d, 1)})
    scored.sort(key=lambda x: x["distance_km"])
    return scored[:max_results]


def _vessel_lat_lon(v: dict[str, Any]) -> tuple[float | None, float | None]:
    """Accept both `lat`/`lon` and `position_lat`/`position_lon` shapes.

    Prefer `lat`/`lon` when present so the fallback registry and any
    normalized vessels take precedence over Phase 4 raw output.
    """
    lat = v.get("lat")
    lon = v.get("lon")
    if lat is None:
        lat = v.get("position_lat")
    if lon is None:
        lon = v.get("position_lon")
    return lat, lon


def vessels_near_origin(
    origin_lat: float,
    origin_lon: float,
    vessels: Iterable[dict[str, Any]],
    radius_km: float = 100.0,
    interception_types: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Return interception-capable vessels within `radius_km` of origin.

    Filters by vessel type (substring match, case-insensitive) against
    `interception_types` (defaults to DEFAULT_INTERCEPTION_TYPES).
    Vessels without coordinates, or with a non-matching type, are skipped.

    Each returned vessel is a shallow copy with an added `distance_km`
    (rounded to 1 decimal). Sorted ascending by distance.
    """
    allowed = tuple(
        t.lower() for t in (interception_types or DEFAULT_INTERCEPTION_TYPES)
    )

    out: list[dict[str, Any]] = []
    for v in vessels:
        v_type = (v.get("type") or v.get("vessel_type") or "").lower()
        if not any(t in v_type for t in allowed):
            continue

        v_lat, v_lon = _vessel_lat_lon(v)
        if v_lat is None or v_lon is None:
            continue

        d = haversine_km(origin_lat, origin_lon, v_lat, v_lon)
        if d <= radius_km:
            out.append({**v, "distance_km": round(d, 1)})

    out.sort(key=lambda x: x["distance_km"])
    return out