"""Phase 8 REST + WebSocket endpoints.

Endpoints:
    WS   /ws/responses                Live alert stream
    GET  /api/responses               Alert history
    POST /api/responses/{id}/ack      Acknowledge an alert
    POST /api/responses/test          Trigger a test alert (demo path)
    GET  /api/stations                List Coast Guard stations
    POST /api/interception-nearby     Vessels near a coordinate

The router is mounted in backend/api/main.py. All persistence reads go
through response_engine's SQLite; all live fan-out goes through the
event_bus singleton.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.notification.event_bus import bus
from backend.notification.geo_utils import (
    nearest_stations,
    vessels_near_origin,
)
from backend.notification.response_engine import (
    DB_PATH,
    _init_db,
    _load_fallback_vessels,
    _load_stations,
    dispatch_response,
)

logger = logging.getLogger(__name__)

# Ensure SQLite alerts table and indexes exist on API startup
try:
    _init_db()
except Exception as exc:
    logger.warning("Could not pre-initialize alerts database: %s", exc)

router = APIRouter(tags=["phase8"])


# ----------------------------------------------------------------------
# Request schemas
# ----------------------------------------------------------------------
class AckRequest(BaseModel):
    acked_by: str = Field(..., min_length=1, max_length=128)


class TestAlertRequest(BaseModel):
    incident_id: str = Field(default="TEST_INCIDENT", max_length=64)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    confidence: float = Field(default=0.96, ge=0, le=1)
    top_suspect_name: str | None = None


class InterceptionQuery(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=100.0, gt=0, le=1000)


# ----------------------------------------------------------------------
# WebSocket — live alert stream
# ----------------------------------------------------------------------
@router.websocket("/ws/responses")
async def ws_responses(ws: WebSocket) -> None:
    """Stream Phase 8 alerts to the dashboard.

    On connect: sends a small hello frame, then streams every alert
    published to the event bus. Never blocks the engine — if the
    dashboard stalls, events are dropped for that client only.
    """
    await ws.accept()
    q = bus.subscribe()
    logger.info("Phase 8 WS: client connected (%d total)", bus.subscriber_count)

    try:
        await ws.send_json({"type": "hello", "subscriber_count": bus.subscriber_count})

        while True:
            # Race the queue against a client disconnect check.
            event = await q.get()
            await ws.send_json({"type": "alert", "data": event})
    except WebSocketDisconnect:
        logger.info("Phase 8 WS: client disconnected")
    except Exception as exc:  # noqa: BLE001 — WS boundary
        logger.warning("Phase 8 WS: error — %s", exc)
    finally:
        bus.unsubscribe(q)


# ----------------------------------------------------------------------
# REST — history and acknowledgement
# ----------------------------------------------------------------------
@router.get("/api/responses")
async def list_responses(limit: int = 50) -> dict[str, Any]:
    """Return recent alerts from SQLite, newest first."""
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit must be between 1 and 500")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM alerts
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    alerts = [_row_to_alert(r) for r in rows]
    return {"count": len(alerts), "alerts": alerts}


@router.post("/api/responses/{alert_id}/ack")
async def ack_response(alert_id: str, body: AckRequest) -> dict[str, Any]:
    """Mark an alert as acknowledged by a duty officer.

    Idempotent — a second ack updates the acked_by/acked_at fields.
    Broadcasts an `ack` frame over the WS so other dashboards update.
    """
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "UPDATE alerts SET acked_by = ?, acked_at = ? WHERE id = ?",
            (body.acked_by, now, alert_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, f"alert {alert_id} not found")
        conn.commit()

    payload = {"id": alert_id, "acked_by": body.acked_by, "acked_at": now}
    bus.publish({"type": "ack", **payload})
    logger.info("Phase 8: alert %s acked by %s", alert_id, body.acked_by)
    return {"status": "ok", **payload}


# ----------------------------------------------------------------------
# REST — demo trigger
# ----------------------------------------------------------------------
@router.post("/api/responses/test")
async def trigger_test_alert(body: TestAlertRequest) -> dict[str, Any]:
    """Fire a test Coast Guard alert through the real dispatch path.

    This is the demo trigger. It calls dispatch_response exactly as the
    pipeline will, so the WS + SMS + SQLite behaviour is identical to
    a live incident.
    """
    incident = {
        "id": body.incident_id,
        "lat": body.lat,
        "lon": body.lon,
        "is_verified_oil": True,
        "filter_confidence": body.confidence,
        "detection_confidence": body.confidence,
        "top_suspect_name": body.top_suspect_name,
    }
    result = await dispatch_response(incident, phase4_vessels=[])
    if result is None:
        raise HTTPException(500, "dispatch_response returned None")
    return result


# ----------------------------------------------------------------------
# REST — station + vessel lookup
# ----------------------------------------------------------------------
@router.get("/api/stations")
async def list_stations() -> dict[str, Any]:
    """Return the full Coast Guard station registry."""
    stations = _load_stations()
    return {"count": len(stations), "stations": stations}


@router.post("/api/interception-nearby")
async def interception_nearby(body: InterceptionQuery) -> dict[str, Any]:
    """Return interception-capable vessels within `radius_km` of a point.

    Uses the static fallback registry (Phase 4 vessels are pipeline-scoped
    and not queryable outside a running pipeline run).
    """
    vessels = vessels_near_origin(
        body.lat,
        body.lon,
        _load_fallback_vessels(),
        radius_km=body.radius_km,
    )
    return {
        "count": len(vessels),
        "radius_km": body.radius_km,
        "origin": {"lat": body.lat, "lon": body.lon},
        "vessels": vessels,
    }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _row_to_alert(row: sqlite3.Row) -> dict[str, Any]:
    """Convert an SQLite row into the frontend alert shape."""
    nearest = json.loads(row["nearest_vessels"]) if row["nearest_vessels"] else []
    return {
        "id": row["id"],
        "incident_id": row["incident_id"],
        "station_id": row["station_id"],
        "station_name": row["station_name"],
        "station_distance_km": row["station_distance_km"],
        "severity": row["severity"],
        "confidence": row["confidence"],
        "top_suspect": row["top_suspect"],
        "interception_count": row["interception_count"],
        "nearest_vessels": nearest,
        "eta_hours": row["eta_hours"],
        "sms_status": row["sms_status"],
        "sms_reason": row["sms_reason"],
        "created_at": row["created_at"],
        "acked_by": row["acked_by"],
        "acked_at": row["acked_at"],
    }