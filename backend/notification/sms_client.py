"""Fast2SMS dispatcher for Phase 8 Coast Guard alerts.

Two modes, controlled independently:

  PHASE8_DRY_RUN=true   (default) → build the message, log it in full,
                                     return {"status": "skipped", ...}.
                                     No network call. This is the mode
                                     used during rehearsal and demos
                                     without a live key.

  PHASE8_DRY_RUN=false  + FAST2SMS_API_KEY set → POST to Fast2SMS,
                                     return {"status": "sent", ...}.

  PHASE8_DRY_RUN=false  + FAST2SMS_API_KEY unset → log a warning, treat
                                     as skipped (fail-safe: never silently
                                     pretend to have sent an SMS).

The returned dict is a stable contract:
    {"status": "sent" | "skipped" | "error", "reason": str | None}
The raw Fast2SMS JSON is never propagated upstream.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

FAST2SMS_ENDPOINT = "https://www.fast2sms.com/dev/bulkV2"
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY", "")

# Read at import time. Restart the process after changing the env var.
DRY_RUN = os.getenv("PHASE8_DRY_RUN", "true").strip().lower() in ("1", "true", "yes")


def _build_message(
    station_name: str,
    incident_id: str,
    lat: float,
    lon: float,
    confidence: float,
    severity: str,
    top_suspect: str | None,
    interception_count: int,
    nearest_vessels: list[str],
    eta_hours: float,
) -> str:
    vessel_line = ", ".join(nearest_vessels[:3]) if nearest_vessels else "none in range"
    return (
        f"[SPILL ALERT — {severity}]\n"
        f"To: {station_name}\n"
        f"Incident: {incident_id}\n"
        f"Location: {lat:.4f}, {lon:.4f}\n"
        f"Confidence: {confidence * 100:.1f}%\n"
        f"Suspect: {top_suspect or 'Under investigation'}\n"
        f"Interception assets within 100 km: {interception_count}\n"
        f"Nearest: {vessel_line}\n"
        f"ETA on-scene: {eta_hours:.1f} h\n"
        f"— Payodhi SIH26143"
    )


def send_coast_guard_alert(
    phone_number: str,
    station_name: str,
    incident_id: str,
    lat: float,
    lon: float,
    confidence: float,
    severity: str,
    top_suspect: str | None,
    interception_count: int,
    nearest_vessels: list[str],
    eta_hours: float,
) -> dict:
    """Dispatch a Coast Guard alert SMS. Returns a stable status dict.

    Returns:
        {"status": "sent",    "reason": None}
        {"status": "skipped", "reason": "dry_run" | "no_api_key"}
        {"status": "error",   "reason": "<error message>"}
    """
    message = _build_message(
        station_name=station_name,
        incident_id=incident_id,
        lat=lat,
        lon=lon,
        confidence=confidence,
        severity=severity,
        top_suspect=top_suspect,
        interception_count=interception_count,
        nearest_vessels=nearest_vessels,
        eta_hours=eta_hours,
    )

    # ---- Dry-run path (no network) ------------------------------------
    if DRY_RUN:
        logger.info(
            "[Phase 8 / SMS DRY-RUN] to=%s\n%s",
            phone_number,
            message,
        )
        print(f"\n--- SMS DRY-RUN (to {phone_number}) ---\n{message}\n--- end ---\n")
        return {"status": "skipped", "reason": "dry_run"}

    # ---- Live path: require key --------------------------------------
    if not FAST2SMS_API_KEY:
        logger.warning(
            "PHASE8_DRY_RUN=false but FAST2SMS_API_KEY is unset — SMS suppressed."
        )
        return {"status": "skipped", "reason": "no_api_key"}

    payload = {
        "route": "q",
        "message": message,
        "language": "english",
        "flash": 0,
        "numbers": phone_number,
    }
    headers = {
        "authorization": FAST2SMS_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        r = requests.post(
            FAST2SMS_ENDPOINT, data=payload, headers=headers, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        # Fast2SMS returns {"return": true, "message": [...]} on success.
        # We do not propagate that shape upstream — just the status.
        if not data.get("return", False):
            reason = str(data.get("message", "provider_rejected"))[:200]
            logger.error("Fast2SMS rejected alert to %s: %s", station_name, reason)
            return {"status": "error", "reason": reason}
        return {"status": "sent", "reason": None}
    except Exception as exc:  # noqa: BLE001 — network/provider boundary
        logger.error("SMS failed for %s: %s", station_name, exc)
        return {"status": "error", "reason": str(exc)[:200]}