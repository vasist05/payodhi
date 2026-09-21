"""Unit tests for Pillar 2: Dark Vessel & AIS Gap Detection."""

from datetime import datetime, timezone
import pytest
from core.phase5_attribution.pillar2_dark_vessel import detect_dark_window


def test_open_ocean_gap_detected():
    """Test suspicious gap > 10 min in open ocean near spill."""
    spill_center = {"lat": 18.0, "lon": 72.0}
    spill_time = datetime(2026, 9, 21, 10, 30, 0, tzinfo=timezone.utc)

    # 40 min gap around spill location
    vessel_track = [
        {"lat": 17.95, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 10, 0, tzinfo=timezone.utc)},
        {"lat": 18.05, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 50, 0, tzinfo=timezone.utc)},
    ]

    res = detect_dark_window(vessel_track, spill_center, spill_time, coastline_distance_nm=20.0)
    assert res["dark_vessel_score"] > 0.5
    assert len(res["gaps"]) == 1
    assert "dark_vessel_anomaly_detected" in res["reason"]


def test_gap_under_10_minutes_ignored():
    """Test gap < 10 min is ignored."""
    spill_center = {"lat": 18.0, "lon": 72.0}
    vessel_track = [
        {"lat": 18.0, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)},
        {"lat": 18.01, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 8, 0, tzinfo=timezone.utc)},  # 8 min
    ]
    res = detect_dark_window(vessel_track, spill_center)
    assert res["dark_vessel_score"] == 0.0
    assert len(res["gaps"]) == 0


def test_gap_beyond_50nm_excluded():
    """Test gap far away from spill (> 50 nm) is excluded."""
    spill_center = {"lat": 18.0, "lon": 72.0}
    # ~150 km (~80 nm) away
    vessel_track = [
        {"lat": 19.5, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)},
        {"lat": 19.6, "lon": 72.0, "time": datetime(2026, 9, 21, 11, 0, 0, tzinfo=timezone.utc)},
    ]
    res = detect_dark_window(vessel_track, spill_center)
    assert res["dark_vessel_score"] == 0.0
    assert res["gaps"][0]["flag"] == "EXCLUDED_BEYOND_50NM"


def test_permanent_blackout_over_24h():
    """Test gap > 24 hours flags PERMANENT_BLACKOUT and scores 0.0."""
    spill_center = {"lat": 18.0, "lon": 72.0}
    vessel_track = [
        {"lat": 18.0, "lon": 72.0, "time": datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)},
        {"lat": 18.1, "lon": 72.0, "time": datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)},  # 36 hours
    ]
    res = detect_dark_window(vessel_track, spill_center)
    assert res["dark_vessel_score"] == 0.0
    assert res["gaps"][0]["flag"] == "PERMANENT_BLACKOUT"
    assert "PERMANENT_BLACKOUT" in res["reason"]


def test_coastal_departure_half_weight():
    """Test gap in coastal waters (<= 5 nm) is weighted at 50%."""
    spill_center = {"lat": 18.0, "lon": 72.0}
    vessel_track = [
        {"lat": 18.0, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)},
        {"lat": 18.05, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 30, 0, tzinfo=timezone.utc)},
    ]
    res_open = detect_dark_window(vessel_track, spill_center, coastline_distance_nm=20.0)
    res_coastal = detect_dark_window(vessel_track, spill_center, coastline_distance_nm=3.0)
    assert pytest.approx(res_coastal["dark_vessel_score"], rel=1e-2) == res_open["dark_vessel_score"] * 0.5


def test_spoofing_speed_jump_halves_score():
    """Test speed jump > 30 knots flags AIS_SPOOFING_SUSPECTED and halves score."""
    spill_center = {"lat": 18.0, "lon": 72.0}
    # Vessel moves ~60 nm in 30 minutes (120 knots jump)
    vessel_track = [
        {"lat": 18.0, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)},
        {"lat": 19.0, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 30, 0, tzinfo=timezone.utc)},
    ]
    res = detect_dark_window(vessel_track, spill_center)
    assert "AIS_SPOOFING_SUSPECTED" in res["reason"]


def test_multiple_gaps_takes_max_not_sum():
    """Test multiple gaps takes the max score rather than summing."""
    spill_center = {"lat": 18.0, "lon": 72.0}
    vessel_track = [
        {"lat": 18.0, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)},
        {"lat": 18.02, "lon": 72.0, "time": datetime(2026, 9, 21, 10, 15, 0, tzinfo=timezone.utc)},  # 15 min gap
        {"lat": 18.05, "lon": 72.0, "time": datetime(2026, 9, 21, 11, 0, 0, tzinfo=timezone.utc)},   # 45 min gap
    ]
    res = detect_dark_window(vessel_track, spill_center)
    assert len(res["gaps"]) == 2
    gap_scores = [g["score"] for g in res["gaps"]]
    assert res["dark_vessel_score"] == max(gap_scores)
    assert res["dark_vessel_score"] < sum(gap_scores)


def test_insufficient_ais_data():
    """Test empty track returns INSUFFICIENT_EVIDENCE."""
    res = detect_dark_window([], {"lat": 18.0, "lon": 72.0})
    assert res["dark_vessel_score"] == 0.0
    assert res["reason"] == "INSUFFICIENT_EVIDENCE"
