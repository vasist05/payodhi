"""Unit tests for Pillar 3: Loitering & Speed Drop Detection."""

from datetime import datetime, timezone
import pytest
from core.phase5_attribution.pillar3_loitering import detect_loitering


def test_standard_loitering_detected():
    """Test cruising ship dropping speed >50% to <5 kn for 40 min within 6h of SAR."""
    sar_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    # 11:00 cruising at 15 kn, then 11:20 to 12:00 at 3 kn (40 min)
    vessel_track = [
        {"lat": 18.0, "lon": 72.0, "time": "2026-09-21T11:00:00Z", "speed": 15.0, "course": 90.0},
        {"lat": 18.05, "lon": 72.0, "time": "2026-09-21T11:20:00Z", "speed": 3.0, "course": 90.0},
        {"lat": 18.06, "lon": 72.0, "time": "2026-09-21T12:00:00Z", "speed": 3.0, "course": 90.0},
        {"lat": 18.15, "lon": 72.0, "time": "2026-09-21T12:30:00Z", "speed": 14.0, "course": 90.0},
    ]
    res = detect_loitering(vessel_track, sar_time)
    assert res["loitering_score"] > 0.0
    assert res["loitering_score"] <= 0.40
    assert len(res["events"]) == 1
    assert "loitering_detected" in res["reason"]


def test_course_change_boost_20_percent():
    """Test course change > 60° while slow boosts score by 20%."""
    sar_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    # Slow for 40 min with heading changing from 30° to 120° (90° turn)
    track_turn = [
        {"lat": 18.0, "lon": 72.0, "time": "2026-09-21T11:00:00Z", "speed": 15.0, "course": 30.0},
        {"lat": 18.05, "lon": 72.0, "time": "2026-09-21T11:20:00Z", "speed": 2.5, "course": 30.0},
        {"lat": 18.06, "lon": 72.0, "time": "2026-09-21T12:00:00Z", "speed": 2.5, "course": 120.0},
    ]
    res_turn = detect_loitering(track_turn, sar_time)
    assert res_turn["events"][0]["course_boost"] is True


def test_outside_six_hour_sar_window_ignored():
    """Test loitering happening 10 hours before SAR scene is ignored."""
    sar_time = datetime(2026, 9, 21, 20, 0, 0, tzinfo=timezone.utc)
    # Slow at 08:00 (12 hours before SAR)
    track_early = [
        {"lat": 18.0, "lon": 72.0, "time": "2026-09-21T07:30:00Z", "speed": 15.0, "course": 0.0},
        {"lat": 18.05, "lon": 72.0, "time": "2026-09-21T08:00:00Z", "speed": 2.0, "course": 0.0},
        {"lat": 18.06, "lon": 72.0, "time": "2026-09-21T08:50:00Z", "speed": 2.0, "course": 0.0},
    ]
    res = detect_loitering(track_early, sar_time)
    assert res["loitering_score"] == 0.0
    assert len(res["events"]) == 0


def test_fishing_vessel_excluded():
    """Test fishing vessel is unconditionally excluded from loitering penalty."""
    sar_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    track = [
        {"lat": 18.0, "lon": 72.0, "time": "2026-09-21T11:00:00Z", "speed": 15.0, "course": 0.0},
        {"lat": 18.05, "lon": 72.0, "time": "2026-09-21T11:20:00Z", "speed": 2.0, "course": 0.0},
        {"lat": 18.06, "lon": 72.0, "time": "2026-09-21T12:00:00Z", "speed": 2.0, "course": 0.0},
    ]
    res = detect_loitering(track, sar_time, vessel_type="fishing")
    assert res["loitering_score"] == 0.0
    assert "fishing_vessel_excluded" in res["reason"]


def test_port_polygon_exclusion():
    """Test loitering inside a designated port polygon is excluded."""
    sar_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    # Port polygon around 18.0 - 18.1, 72.0 - 72.1
    port_poly = [[17.9, 71.9], [18.2, 71.9], [18.2, 72.2], [17.9, 72.2]]
    track_in_port = [
        {"lat": 18.0, "lon": 72.0, "time": "2026-09-21T11:00:00Z", "speed": 12.0, "course": 0.0},
        {"lat": 18.05, "lon": 72.0, "time": "2026-09-21T11:20:00Z", "speed": 2.0, "course": 0.0},
        {"lat": 18.06, "lon": 72.0, "time": "2026-09-21T12:00:00Z", "speed": 2.0, "course": 0.0},
    ]
    res = detect_loitering(track_in_port, sar_time, port_polygons=[port_poly])
    assert res["loitering_score"] == 0.0
    assert len(res["events"]) == 0


def test_short_slow_period_under_30_min_ignored():
    """Test slow event lasting only 10 minutes is ignored."""
    sar_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    track_short = [
        {"lat": 18.0, "lon": 72.0, "time": "2026-09-21T11:00:00Z", "speed": 15.0, "course": 0.0},
        {"lat": 18.05, "lon": 72.0, "time": "2026-09-21T11:20:00Z", "speed": 2.0, "course": 0.0},
        {"lat": 18.06, "lon": 72.0, "time": "2026-09-21T11:30:00Z", "speed": 2.0, "course": 0.0},  # 10 min
        {"lat": 18.15, "lon": 72.0, "time": "2026-09-21T11:35:00Z", "speed": 15.0, "course": 0.0},
    ]
    res = detect_loitering(track_short, sar_time)
    assert res["loitering_score"] == 0.0


def test_score_capped_at_point_four():
    """Test that score is capped at 0.40 even for extreme loitering."""
    sar_time = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)
    track_long = [
        {"lat": 18.0, "lon": 72.0, "time": "2026-09-21T10:00:00Z", "speed": 20.0, "course": 0.0},
        {"lat": 18.01, "lon": 72.0, "time": "2026-09-21T10:30:00Z", "speed": 1.0, "course": 0.0},
        {"lat": 18.02, "lon": 72.0, "time": "2026-09-21T12:00:00Z", "speed": 1.0, "course": 180.0},  # 90 min, 180° turn
    ]
    res = detect_loitering(track_long, sar_time)
    assert res["loitering_score"] <= 0.40
