"""SMS dispatcher for Phase 8 Coast Guard alerts.

Supports:
  1. SMSGatewayHub (default / sandbox / production)
  2. Fast2SMS (bulkV2 Quick SMS)
  3. Dry-run mode (PHASE8_DRY_RUN=true) for local simulation without network calls

Phone Number Handling:
  - If ALERT_PHONE_OVERRIDE is set in environment, alerts will be directed to that
    test phone number (useful during demos and evaluation).
  - Automatically cleans and formats 10-digit Indian numbers with standard country prefix.

Contract:
  send_coast_guard_alert(...) -> {"status": "sent" | "skipped" | "error", "reason": str | None}
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any
import requests

logger = logging.getLogger(__name__)

# Providers
SMSGATEWAYHUB_ENDPOINT = "https://www.smsgatewayhub.com/api/mt/SendSMS"
FAST2SMS_ENDPOINT = "https://www.fast2sms.com/dev/bulkV2"


def _is_dry_run() -> bool:
    return os.getenv("PHASE8_DRY_RUN", "true").strip().lower() in ("1", "true", "yes")


def _get_provider() -> str:
    return os.getenv("SMS_PROVIDER", "smsgatewayhub").strip().lower()


def _sanitize_phone(phone: str) -> str:
    """Extract digits and format for Indian SMS gateways."""
    override = os.getenv("ALERT_PHONE_OVERRIDE", "").strip()
    target = override if override else phone
    digits = re.sub(r"\D", "", target)

    # If it's a 10-digit number, prepend 91 for Indian gateways
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    return digits


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


def _send_smsgatewayhub(number: str, message: str, station_name: str) -> dict[str, Any]:
    api_key = os.getenv("SMSGATEWAYHUB_API_KEY", "").strip()
    if not api_key:
        logger.warning("PHASE8_DRY_RUN=false but SMSGATEWAYHUB_API_KEY is unset.")
        return {"status": "skipped", "reason": "no_api_key"}

    sender_id = os.getenv("SMSGATEWAYHUB_SENDER_ID", "TESTIN").strip()
    channel = os.getenv("SMSGATEWAYHUB_CHANNEL", "2").strip()
    route = os.getenv("SMSGATEWAYHUB_ROUTE", "1").strip()
    dcs = os.getenv("SMSGATEWAYHUB_DCS", "0").strip()

    params = {
        "APIKey": api_key,
        "senderid": sender_id,
        "channel": channel,
        "DCS": dcs,
        "number": number,
        "text": message,
        "route": route,
    }

    try:
        r = requests.get(SMSGATEWAYHUB_ENDPOINT, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        error_code = str(data.get("ErrorCode", ""))
        status = str(data.get("Status", "")).lower()

        if error_code == "000" or status == "success":
            logger.info("SMSGatewayHub delivered alert to %s (%s)", station_name, number)
            return {"status": "sent", "reason": None}

        reason = str(data.get("ErrorMessage") or data.get("Description") or "gateway_rejected")[:200]
        logger.error("SMSGatewayHub error for %s: %s (code=%s)", station_name, reason, error_code)
        return {"status": "error", "reason": reason}
    except Exception as exc:  # noqa: BLE001
        logger.error("SMSGatewayHub network failure for %s: %s", station_name, exc)
        return {"status": "error", "reason": str(exc)[:200]}


def _send_fast2sms(number: str, message: str, station_name: str) -> dict[str, Any]:
    api_key = os.getenv("FAST2SMS_API_KEY", "").strip()
    if not api_key:
        logger.warning("PHASE8_DRY_RUN=false but FAST2SMS_API_KEY is unset.")
        return {"status": "skipped", "reason": "no_api_key"}

    # Fast2SMS requires 10-digit number without 91 prefix
    clean_10 = number[-10:] if len(number) >= 10 else number

    payload = {
        "route": "q",
        "message": message,
        "language": "english",
        "flash": 0,
        "numbers": clean_10,
    }
    headers = {
        "authorization": api_key,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        r = requests.post(FAST2SMS_ENDPOINT, data=payload, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not data.get("return", False):
            reason = str(data.get("message", "provider_rejected"))[:200]
            logger.error("Fast2SMS rejected alert to %s: %s", station_name, reason)
            return {"status": "error", "reason": reason}
        return {"status": "sent", "reason": None}
    except Exception as exc:  # noqa: BLE001
        logger.error("Fast2SMS failed for %s: %s", station_name, exc)
        return {"status": "error", "reason": str(exc)[:200]}


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
) -> dict[str, Any]:
    """Dispatch a Coast Guard alert SMS. Returns a stable status dict.

    Returns:
        {"status": "sent",    "reason": None}
        {"status": "skipped", "reason": "dry_run" | "no_api_key" | "invalid_number"}
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

    clean_number = _sanitize_phone(phone_number)

    # ---- Dry-run path (no network) ------------------------------------
    if _is_dry_run():
        logger.info(
            "[Phase 8 / SMS DRY-RUN] to=%s (%s)\n%s",
            clean_number or phone_number,
            station_name,
            message,
        )
        print(f"\n--- SMS DRY-RUN (to {clean_number or phone_number} | {station_name}) ---\n{message}\n--- end ---\n")
        return {"status": "skipped", "reason": "dry_run"}

    # ---- Validate number ----------------------------------------------
    if not clean_number or len(clean_number) < 10 or "X" in clean_number:
        logger.warning(
            "SMS skipped: invalid/placeholder phone number '%s' for %s (Set ALERT_PHONE_OVERRIDE in .env to test with your mobile).",
            phone_number,
            station_name,
        )
        return {"status": "skipped", "reason": "invalid_number"}

    # ---- Dispatch by provider -----------------------------------------
    provider = _get_provider()
    if provider == "smsgatewayhub":
        return _send_smsgatewayhub(clean_number, message, station_name)
    elif provider == "fast2sms":
        return _send_fast2sms(clean_number, message, station_name)
    else:
        logger.error("Unknown SMS_PROVIDER: '%s'", provider)
        return {"status": "error", "reason": f"unknown_provider_{provider}"}