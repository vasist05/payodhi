"""Unit tests for Pillar 5: Waterline Displacement (Draft Change)."""

from datetime import datetime, timezone
import pytest
from core.phase5_attribution.pillar5_draft_change import draft_change_score


def test_valid_draft_decrease_detected():
    """Test valid draft decrease >= 0.5m yields positive score <= 0.80."""
    spill_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    # 3 readings before (median = 12.0m), 3 readings after (median = 11.0m) -> delta = 1.0m
    history = [
        {"draft_meters": 12.1, "timestamp": "2026-09-21T09:00:00Z"},
        {"draft_meters": 12.0, "timestamp": "2026-09-21T10:00:00Z"},
        {"draft_meters": 11.9, "timestamp": "2026-09-21T11:00:00Z"},
        {"draft_meters": 11.0, "timestamp": "2026-09-21T13:00:00Z"},
        {"draft_meters": 11.0, "timestamp": "2026-09-21T14:00:00Z"},
        {"draft_meters": 10.9, "timestamp": "2026-09-21T15:00:00Z"},
    ]
    res = draft_change_score(history, spill_time)
    assert res["draft_change_score"] > 0.0
    assert res["draft_change_score"] <= 0.80
    assert res["draft_before"] == 12.0
    assert res["draft_after"] == 11.0
    assert "significant_draft_decrease_detected" in res["reason"]


def test_edge_case_insufficient_readings():
    """Edge case 1: < 2 readings returns score=0.0 and insufficient_draft_data."""
    spill_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    res_empty = draft_change_score([], spill_time)
    assert res_empty["draft_change_score"] == 0.0
    assert "insufficient_draft_data" in res_empty["reason"]

    res_single = draft_change_score([{"draft_meters": 10.0, "timestamp": "2026-09-21T10:00:00Z"}], spill_time)
    assert res_single["draft_change_score"] == 0.0
    assert "insufficient_draft_data" in res_single["reason"]


def test_edge_case_all_drafts_identical():
    """Edge case 2: All drafts identical returns score=0.0."""
    spill_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    history = [
        {"draft_meters": 10.5, "timestamp": "2026-09-21T10:00:00Z"},
        {"draft_meters": 10.5, "timestamp": "2026-09-21T11:00:00Z"},
        {"draft_meters": 10.5, "timestamp": "2026-09-21T13:00:00Z"},
    ]
    res = draft_change_score(history, spill_time)
    assert res["draft_change_score"] == 0.0
    assert res["draft_before"] == 10.5
    assert res["draft_after"] == 10.5
    assert "all_drafts_identical" in res["reason"]


def test_edge_case_large_decrease_over_5m_capped():
    """Edge case 3: Decrease > 5m caps score at 0.80 and flags DATA_ERROR_LARGE_CHANGE."""
    spill_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    # Draft drops from 15.0m to 8.0m (7m drop)
    history = [
        {"draft_meters": 15.0, "timestamp": "2026-09-21T10:00:00Z"},
        {"draft_meters": 8.0, "timestamp": "2026-09-21T14:00:00Z"},
    ]
    res = draft_change_score(history, spill_time)
    assert res["draft_change_score"] == 0.80
    assert "DATA_ERROR_LARGE_CHANGE" in res["reason"]


def test_edge_case_ballast_taken_draft_increase():
    """Edge case 4: Draft increase returns score=0.0 and reason='ballast_taken'."""
    spill_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    # Draft increases from 9.0m to 11.0m
    history = [
        {"draft_meters": 9.0, "timestamp": "2026-09-21T10:00:00Z"},
        {"draft_meters": 11.0, "timestamp": "2026-09-21T14:00:00Z"},
    ]
    res = draft_change_score(history, spill_time)
    assert res["draft_change_score"] == 0.0
    assert "ballast_taken" in res["reason"]


def test_edge_case_fishing_vessel_excluded():
    """Edge case 5: Fishing vessel excluded returns score=0.0 and fishing_vessel_excluded."""
    spill_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    history = [
        {"draft_meters": 4.0, "timestamp": "2026-09-21T10:00:00Z"},
        {"draft_meters": 3.0, "timestamp": "2026-09-21T14:00:00Z"},
    ]
    res = draft_change_score(history, spill_time, vessel_type="fishing")
    assert res["draft_change_score"] == 0.0
    assert "fishing_vessel_excluded" in res["reason"]


def test_edge_case_voyage_spans_over_30_days():
    """Edge case 6: Voyage spans > 30 days filters only readings within 48h of spill."""
    spill_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    # History spans 40 days; old reading should be filtered out
    history = [
        {"draft_meters": 15.0, "timestamp": "2026-08-10T10:00:00Z"},  # 42 days earlier
        {"draft_meters": 12.0, "timestamp": "2026-09-21T08:00:00Z"},  # 4h before spill
        {"draft_meters": 11.0, "timestamp": "2026-09-21T16:00:00Z"},  # 4h after spill
    ]
    res = draft_change_score(history, spill_time)
    assert res["draft_before"] == 12.0
    assert res["draft_after"] == 11.0
    assert res["draft_change_score"] > 0.0
