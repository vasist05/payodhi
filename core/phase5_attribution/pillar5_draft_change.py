"""Pillar 5: Waterline Displacement (Draft Change).

Compares vessel draft before vs after a spill event using vessel_static_history.
Adheres strictly to phase5Final.md Pillar 5 rules:
- Read draft_meters from vessel_static_history records.
- Compare median of 3 readings before vs after spill.
- Only flag if draft decreases by >= 0.5m (draft increase = ballast taken, score = 0.0).
- Exclude fishing vessels (score = 0.0, reason = "fishing_vessel_excluded").
- Skip if < 2 readings exist (score = 0.0, reason = "insufficient_draft_data").
- All drafts identical -> score = 0.0.
- Draft decrease > 5m -> cap score at 0.8, flag DATA_ERROR_LARGE_CHANGE.
- Voyage spans > 30 days -> use only readings within 48h of spill.
- Cap score at 0.80.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import statistics
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

MAX_DRAFT_SCORE = 0.80
MIN_DRAFT_DECREASE_THRESHOLD_M = 0.50
LARGE_DECREASE_THRESHOLD_M = 5.00


def _parse_timestamp(t: Any) -> datetime:
    if t is None:
        raise ValueError("Timestamp cannot be None")
    if isinstance(t, datetime):
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc)
    if isinstance(t, (int, float)):
        return datetime.fromtimestamp(t, tz=timezone.utc)
    if isinstance(t, str):
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raise TypeError(f"Unsupported timestamp type: {type(t).__name__}")


def draft_change_score(
    vessel_static_history: Optional[List[Dict[str, Any]]],
    spill_time: Union[datetime, str, float],
    vessel_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculate Pillar 5 attribution score based on waterline displacement.

    Args:
        vessel_static_history: List of dicts with draft_meters and timestamp.
        spill_time: Timestamp of the spill / SAR detection.
        vessel_type: Optional vessel type classification string.

    Returns:
        dict:
            draft_change_score (float): Attribution score capped at 0.80.
            draft_before (float or None): Median draft before spill (meters).
            draft_after (float or None): Median draft after spill (meters).
            reason (str): Explanatory reason and edge case flags.
    """
    # Edge case 5: Fishing vessel excluded
    norm_type = (vessel_type or "").strip().lower()
    if not norm_type and vessel_static_history and "vessel_type" in vessel_static_history[0]:
        norm_type = str(vessel_static_history[0]["vessel_type"]).strip().lower()

    if norm_type == "fishing":
        logger.info("Fishing vessel draft is unreliable; skipping Pillar 5.")
        return {
            "draft_change_score": 0.0,
            "draft_before": None,
            "draft_after": None,
            "reason": "fishing_vessel_excluded",
        }

    # Edge case 1: < 2 readings
    if not vessel_static_history or len(vessel_static_history) < 2:
        return {
            "draft_change_score": 0.0,
            "draft_before": None,
            "draft_after": None,
            "reason": "insufficient_draft_data",
        }

    parsed_spill_time = _parse_timestamp(spill_time)

    # Parse and sort readings
    parsed_readings = []
    for r in vessel_static_history:
        draft = r.get("draft_meters") if "draft_meters" in r else r.get("draft", r.get("draught"))
        t_val = r.get("timestamp") if "timestamp" in r else r.get("time")
        if draft is not None and t_val is not None:
            parsed_readings.append({
                "draft": float(draft),
                "time": _parse_timestamp(t_val),
            })

    parsed_readings.sort(key=lambda x: x["time"])

    if len(parsed_readings) < 2:
        return {
            "draft_change_score": 0.0,
            "draft_before": None,
            "draft_after": None,
            "reason": "insufficient_draft_data",
        }

    # Edge case 6: Voyage spans > 30 days -> use only readings within 48h of spill
    timespan = parsed_readings[-1]["time"] - parsed_readings[0]["time"]
    if timespan > timedelta(days=30):
        logger.info("Voyage timespan > 30 days. Filtering to readings within 48h of spill.")
        filtered = [
            r for r in parsed_readings
            if abs((r["time"] - parsed_spill_time).total_seconds()) <= 48 * 3600
        ]
        if len(filtered) < 2:
            return {
                "draft_change_score": 0.0,
                "draft_before": None,
                "draft_after": None,
                "reason": "insufficient_draft_data (filtered_within_48h_of_spill)",
            }
        parsed_readings = filtered

    # Edge case 2: All drafts identical
    all_drafts = [r["draft"] for r in parsed_readings]
    if all(d == all_drafts[0] for d in all_drafts):
        return {
            "draft_change_score": 0.0,
            "draft_before": round(all_drafts[0], 2),
            "draft_after": round(all_drafts[0], 2),
            "reason": "all_drafts_identical",
        }

    # Partition into readings before vs after spill
    before_readings = [r["draft"] for r in parsed_readings if r["time"] <= parsed_spill_time]
    after_readings = [r["draft"] for r in parsed_readings if r["time"] > parsed_spill_time]

    # If all readings are on one side of the spill, compare first vs second half
    if not before_readings or not after_readings:
        mid_idx = len(parsed_readings) // 2
        before_readings = [r["draft"] for r in parsed_readings[:mid_idx]]
        after_readings = [r["draft"] for r in parsed_readings[mid_idx:]]

    if not before_readings or not after_readings:
        return {
            "draft_change_score": 0.0,
            "draft_before": None,
            "draft_after": None,
            "reason": "insufficient_draft_data",
        }

    # Compare median of up to 3 readings before vs after
    sample_before = before_readings[-3:]
    sample_after = after_readings[:3]

    draft_before = round(statistics.median(sample_before), 3)
    draft_after = round(statistics.median(sample_after), 3)

    delta_draft = draft_before - draft_after  # Positive when vessel discharged mass (floats higher)

    # Edge case 4: Draft increase -> ballast taken, score = 0.0
    if delta_draft < 0:
        return {
            "draft_change_score": 0.0,
            "draft_before": draft_before,
            "draft_after": draft_after,
            "reason": f"ballast_taken (draft increased by {-delta_draft:.2f}m)",
        }

    # Below detection threshold < 0.5m
    if delta_draft < MIN_DRAFT_DECREASE_THRESHOLD_M:
        return {
            "draft_change_score": 0.0,
            "draft_before": draft_before,
            "draft_after": draft_after,
            "reason": f"draft_change_below_threshold (delta={delta_draft:.2f}m < 0.5m)",
        }

    # Edge case 3: Draft decrease > 5m -> cap at 0.8, flag DATA_ERROR_LARGE_CHANGE
    if delta_draft > LARGE_DECREASE_THRESHOLD_M:
        logger.warning("Draft decrease %.2fm > 5m; likely data entry error. Capped at 0.8.", delta_draft)
        return {
            "draft_change_score": MAX_DRAFT_SCORE,
            "draft_before": draft_before,
            "draft_after": draft_after,
            "reason": f"DATA_ERROR_LARGE_CHANGE (draft decreased by {delta_draft:.2f}m > 5m, capped at 0.8)",
        }

    # Calculate score scaling from 0.5m (0.40) to 2.5m (0.80), strictly capped at 0.80
    raw_score = 0.40 + ((delta_draft - 0.50) / 2.00) * 0.40
    final_score = min(MAX_DRAFT_SCORE, max(0.0, raw_score))

    return {
        "draft_change_score": round(final_score, 3),
        "draft_before": draft_before,
        "draft_after": draft_after,
        "reason": f"significant_draft_decrease_detected (delta={delta_draft:.2f}m)",
    }
