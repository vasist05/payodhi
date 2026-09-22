"""Phase 8 response engine.

Orchestrates a Coast Guard alert from a verified incident:
    1. Load station + fallback vessel registries (lazy, cached)
    2. Gate on is_verified_oil and filter_confidence >= MIN_CONFIDENCE
    3. Cooldown: skip if the primary station already alerted recently
    4. Select nearest 3 stations; primary = closest
    5. Merge Phase 4 vessels with fallback registry, dedupe by MMSI
    6. Count interception-capable vessels within INTERCEPTION_RADIUS_KM
    7. ETA = primary station distance / cruise speed
    8. Persist alert to SQLite
    9. Publish alert to the event bus (WebSocket fan-out)
   10. Dispatch SMS to the primary station (respects PHASE8_DRY_RUN)

The engine is import-safe with no server running: Test 2 exercises the
full path with no API layer and no live SMS.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.notification.event_bus import bus
from backend.notification.geo_utils import nearest_stations, vessels_near_origin
from backend.notification.sms_client import send_coast_guard_alert

logger = logging.getLogger(__name__)

# ---- Tuning constants -------------------------------------------------
INTERCEPTION_CRUISE_SPEED_KNOTS = 18.0   # typical ICG patrol-vessel cruise
KNOTS_TO_KMH = 1.852                     # 1 knot = 1.852 km/h
INTERCEPTION_RADIUS_KM = 100.0
MIN_CONFIDENCE = 0.75
COOLDOWN_MINUTES = 30
MAX_BACKUP_STATIONS = 2                  # primary + 2 backups = 3 total

# Severity thresholds (filter_confidence bands) ------------------------
SEVERITY_HIGH_THRESHOLD = 0.90

# ---- Paths ------------------------------------------------------------
_PKG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _PKG_DIR.parent.parent
STATIONS_PATH = PROJECT_ROOT / "data" / "response" / "coast_guard_stations.json"
VESSELS_PATH = PROJECT_ROOT / "data" / "response" / "interception_vessels.json"
DB_PATH = _PKG_DIR / "alerts.db"

# ---- Lazy-loaded registries ------------------------------------------
_stations_cache: list[dict[str, Any]] | None = None
_vessels_cache: list[dict[str, Any]] | None = None


def _load_stations() -> list[dict[str, Any]]:
    global _stations_cache
    if _stations_cache is None:
        with open(STATIONS_PATH, "r", encoding="utf-8") as f:
            _stations_cache = json.load(f)
    return _stations_cache


def _load_fallback_vessels() -> list[dict[str, Any]]:
    global _vessels_cache
    if _vessels_cache is None:
        with open(VESSELS_PATH, "r", encoding="utf-8") as f:
            _vessels_cache = json.load(f)
    return _vessels_cache


# ---- SQLite -----------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id                  TEXT PRIMARY KEY,
    incident_id         TEXT NOT NULL,
    station_id          TEXT NOT NULL,
    station_name        TEXT NOT NULL,
    station_distance_km REAL NOT NULL,
    severity            TEXT NOT NULL,
    confidence          REAL NOT NULL,
    top_suspect         TEXT,
    interception_count  INTEGER NOT NULL,
    nearest_vessels     TEXT NOT NULL,
    eta_hours           REAL NOT NULL,
    sms_status          TEXT NOT NULL,
    sms_reason          TEXT,
    created_at          TEXT NOT NULL,
    acked_by            TEXT,
    acked_at            TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_station_created
    ON alerts (station_id, created_at);
"""


def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _db_connect() as conn:
        conn.executescript(_SCHEMA)


def _persist_alert(alert: dict[str, Any]) -> None:
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO alerts (
                id, incident_id, station_id, station_name, station_distance_km,
                severity, confidence, top_suspect, interception_count,
                nearest_vessels, eta_hours, sms_status, sms_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert["id"],
                alert["incident_id"],
                alert["station_id"],
                alert["station_name"],
                alert["station_distance_km"],
                alert["severity"],
                alert["confidence"],
                alert.get("top_suspect"),
                alert["interception_count"],
                json.dumps(alert["nearest_vessels"]),
                alert["eta_hours"],
                alert["sms"]["status"],
                alert["sms"].get("reason"),
                alert["created_at"],
            ),
        )


def _recent_alert_exists(station_id: str, within_minutes: int) -> bool:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
    ).isoformat()
    with _db_connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM alerts WHERE station_id = ? AND created_at >= ? LIMIT 1",
            (station_id, cutoff),
        ).fetchone()
    return row is not None


# ---- Helpers ----------------------------------------------------------
def _merge_vessels(
    phase4_vessels: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Merge Phase 4 vessels with the static fallback registry.

    Dedupes by MMSI. Phase 4 vessels win on conflict — they carry live
    position data. The fallback registry is only used to fill in assets
    that Phase 4 didn't report (or when Phase 4 is absent entirely).
    """
    by_mmsi: dict[str, dict[str, Any]] = {}

    for v in _load_fallback_vessels():
        mmsi = v.get("mmsi")
        if mmsi:
            by_mmsi[mmsi] = v

    for v in phase4_vessels or []:
        mmsi = v.get("mmsi")
        if mmsi:
            by_mmsi[mmsi] = v  # overrides fallback
        else:
            # No MMSI — keep it, keyed by name so it isn't dropped.
            key = f"_name:{v.get('name', 'unknown')}"
            by_mmsi[key] = v

    return list(by_mmsi.values())


def _severity(confidence: float) -> str:
    return "HIGH" if confidence >= SEVERITY_HIGH_THRESHOLD else "MODERATE"


def _eta_hours(distance_km: float) -> float:
    speed_kmh = INTERCEPTION_CRUISE_SPEED_KNOTS * KNOTS_TO_KMH
    return round(distance_km / speed_kmh, 2)


# ---- Public API -------------------------------------------------------
async def dispatch_response(
    incident: dict[str, Any],
    phase4_vessels: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Dispatch a Coast Guard alert for a verified incident.

    Returns the alert dict on success, or a suppression dict
    ({"status": "suppressed", "reason": ...}) if gating failed.
    Never raises for expected suppression; raises only on unexpected
    internal errors (caller should wrap in try/except if desired).
    """
    _init_db()

    incident_id = incident.get("id") or f"INC_{uuid.uuid4().hex[:8]}"
    is_verified = bool(incident.get("is_verified_oil"))
    confidence = float(
        incident.get("filter_confidence")
        or incident.get("detection_confidence")
        or 0.0
    )
    lat = incident.get("lat")
    lon = incident.get("lon")
    top_suspect = incident.get("top_suspect_name")

    # ---- Gate 1: verified oil -----------------------------------------
    if not is_verified:
        logger.info("Phase 8: incident %s not verified — suppressed", incident_id)
        return {"status": "suppressed", "reason": "not_verified_oil"}

    if lat is None or lon is None:
        logger.warning("Phase 8: incident %s missing coordinates", incident_id)
        return {"status": "suppressed", "reason": "missing_coordinates"}

    # ---- Gate 2: confidence -------------------------------------------
    if confidence < MIN_CONFIDENCE:
        logger.info(
            "Phase 8: incident %s confidence %.2f < %.2f — suppressed",
            incident_id, confidence, MIN_CONFIDENCE,
        )
        return {"status": "suppressed", "reason": "below_confidence_threshold"}

    # ---- Station selection --------------------------------------------
    stations = nearest_stations(
        lat, lon,
        _load_stations(),
        max_results=1 + MAX_BACKUP_STATIONS,
    )
    if not stations:
        logger.warning("Phase 8: no station within search bound of %s", incident_id)
        return {"status": "suppressed", "reason": "no_station_in_range"}

    primary = stations[0]
    backups = stations[1:]

    # ---- Gate 3: cooldown ---------------------------------------------
    if _recent_alert_exists(primary["id"], COOLDOWN_MINUTES):
        logger.info(
            "Phase 8: station %s alerted within %d min — suppressed",
            primary["id"], COOLDOWN_MINUTES,
        )
        return {
            "status": "suppressed",
            "reason": "cooldown",
            "station_id": primary["id"],
        }

    # ---- Interception asset count -------------------------------------
    merged = _merge_vessels(phase4_vessels)
    nearby = vessels_near_origin(
        lat, lon,
        merged,
        radius_km=INTERCEPTION_RADIUS_KM,
    )
    nearest_names = [v.get("name", "unknown") for v in nearby]

    # ---- ETA ----------------------------------------------------------
    eta = _eta_hours(primary["distance_km"])
    severity = _severity(confidence)

    # ---- Build alert dict ---------------------------------------------
    alert_id = f"ALERT_{uuid.uuid4().hex[:10]}"
    created_at = datetime.now(timezone.utc).isoformat()

    alert: dict[str, Any] = {
        "id": alert_id,
        "incident_id": incident_id,
        "station_id": primary["id"],
        "station_name": primary["name"],
        "station_distance_km": primary["distance_km"],
        "backup_stations": [s["name"] for s in backups],
        "severity": severity,
        "confidence": round(confidence, 3),
        "top_suspect": top_suspect,
        "interception_count": len(nearby),
        "nearest_vessels": nearest_names[:5],
        "eta_hours": eta,
        "created_at": created_at,
        "sms": {"status": "pending", "reason": None},
    }

    # ---- SMS ----------------------------------------------------------
    # Dry-run or live, this never raises; returns a stable status dict.
    sms_result = send_coast_guard_alert(
        phone_number=primary.get("phone", ""),
        station_name=primary["name"],
        incident_id=incident_id,
        lat=lat,
        lon=lon,
        confidence=confidence,
        severity=severity,
        top_suspect=top_suspect,
        interception_count=len(nearby),
        nearest_vessels=nearest_names,
        eta_hours=eta,
    )
    alert["sms"] = sms_result

    # ---- Persist ------------------------------------------------------
    _persist_alert(alert)

    # ---- Publish to event bus (WebSocket fan-out) ---------------------
    bus.publish(alert)

    logger.info(
        "Phase 8: alert %s dispatched -> %s (%.1f km, %d assets, ETA %.1fh, sms=%s)",
        alert_id, primary["name"], primary["distance_km"],
        len(nearby), eta, sms_result["status"],
    )
    return alert