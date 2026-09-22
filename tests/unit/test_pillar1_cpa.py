"""Unit tests for Pillar 1: Closest Point of Approach (CPA) calculation."""

from datetime import datetime, timezone
import pytest
import pyproj

from core.phase5_attribution.pillar1_cpa import calculate_cpa


def test_cpa_exact_timestamp_match():
    """Test CPA when both vessel track and drift trajectory have identical timestamps."""
    t0 = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 21, 10, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 21, 10, 20, 0, tzinfo=timezone.utc)

    # Vessel moving north along 72.0 longitude
    vessel_track = [
        {"lat": 18.0, "lon": 72.0, "time": t0},
        {"lat": 18.1, "lon": 72.0, "time": t1},
        {"lat": 18.2, "lon": 72.0, "time": t2},
    ]

    # Drift trajectory moving east, crossing near (18.1, 72.0) at t1
    drift_trajectory = [
        {"lat": 18.1, "lon": 71.9, "time": t0},
        {"lat": 18.1, "lon": 72.0005, "time": t1},  # ~52.8m from vessel at t1
        {"lat": 18.1, "lon": 72.1, "time": t2},
    ]

    result = calculate_cpa(vessel_track, drift_trajectory)

    # Validate output dictionary schema
    assert "min_distance_m" in result
    assert "cpa_timestamp" in result
    assert "tcpa_seconds" in result
    assert "cpa_score" in result
    assert "low_confidence" in result

    # Check CPA occurs at t1
    assert result["cpa_timestamp"] == t1
    assert result["tcpa_seconds"] == 600.0
    assert result["cpa_score"] == 1.0  # < 100m distance yields 1.0

    # Verify distance matches WGS84 geodesic calculation
    geod = pyproj.Geod(ellps="WGS84")
    _, _, expected_dist = geod.inv(72.0, 18.1, 72.0005, 18.1)
    assert pytest.approx(result["min_distance_m"], abs=0.01) == round(expected_dist, 3)
    assert result["min_distance_m"] < 100.0


def test_cpa_tcpa_sign():
    """Test TCPA sign: positive if CPA is in future relative to ref_time, negative if in past."""
    t_past = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)
    t_now = datetime(2026, 9, 21, 10, 30, 0, tzinfo=timezone.utc)
    t_future = datetime(2026, 9, 21, 11, 0, 0, tzinfo=timezone.utc)

    vessel_track = [
        {"lat": 15.0, "lon": 70.0, "time": t_past},
        {"lat": 15.1, "lon": 70.0, "time": t_future},
    ]
    # CPA at t_past
    drift_past_cpa = [
        {"lat": 15.0001, "lon": 70.0, "time": t_past},
        {"lat": 16.0, "lon": 70.0, "time": t_future},
    ]
    res_past = calculate_cpa(vessel_track, drift_past_cpa, reference_time=t_now)
    assert res_past["tcpa_seconds"] < 0  # Past CPA is negative

    # CPA at t_future
    drift_future_cpa = [
        {"lat": 16.0, "lon": 70.0, "time": t_past},
        {"lat": 15.1001, "lon": 70.0, "time": t_future},
    ]
    res_future = calculate_cpa(vessel_track, drift_future_cpa, reference_time=t_now)
    assert res_future["tcpa_seconds"] > 0  # Future CPA is positive


def test_cpa_duplicate_timestamps_deduplicated():
    """Test that duplicate timestamps in tracks are deduplicated, keeping the last observation."""
    t0 = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 21, 10, 10, 0, tzinfo=timezone.utc)

    # Duplicate point at t1 with corrected position
    vessel_track = [
        {"lat": 12.0, "lon": 75.0, "time": t0},
        {"lat": 12.05, "lon": 75.0, "time": t1},
        {"lat": 12.1, "lon": 75.0, "time": t1},  # Last observation should be kept
    ]
    drift_trajectory = [
        {"lat": 11.9, "lon": 75.0, "time": t0},  # ~11 km away at t0
        {"lat": 12.1, "lon": 75.0, "time": t1},  # 0m away at t1
    ]

    result = calculate_cpa(vessel_track, drift_trajectory)
    assert result["cpa_timestamp"] == t1
    assert result["vessel_point"]["lat"] == 12.1  # Verified last point retained


def test_cpa_all_points_identical_stationary():
    """Test edge case: all track points identical returns cpa_score = 0.0."""
    t0 = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 21, 10, 10, 0, tzinfo=timezone.utc)

    vessel_track = [
        {"lat": 10.0, "lon": 70.0, "time": t0},
        {"lat": 10.0, "lon": 70.0, "time": t1},
    ]
    drift_trajectory = [
        {"lat": 10.0001, "lon": 70.0, "time": t0},
        {"lat": 10.0002, "lon": 70.0, "time": t1},
    ]

    result = calculate_cpa(vessel_track, drift_trajectory)
    assert result["cpa_score"] == 0.0


def test_cpa_alignment_gap_over_30min_halves_score():
    """Test edge case: time alignment gap > 30 minutes flags LOW_CONFIDENCE and halves score."""
    t0 = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 21, 10, 45, 0, tzinfo=timezone.utc)  # 45 min gap (> 30 min)

    vessel_track = [
        {"lat": 10.0, "lon": 70.0, "time": t0},
        {"lat": 10.1, "lon": 70.0, "time": t1},
    ]
    drift_trajectory = [
        {"lat": 10.0001, "lon": 70.0, "time": t0},
        {"lat": 10.1001, "lon": 70.0, "time": t1},
    ]

    result = calculate_cpa(vessel_track, drift_trajectory)
    assert result["low_confidence"] is True
    # Under 100m would normally be 1.0, but due to gap penalty it is halved to 0.5
    assert result["cpa_score"] == 0.5


def test_cpa_edge_case_empty_drift_or_short_vessel():
    """Test edge case: empty drift trajectory or vessel track < 2 points."""
    # Drift empty
    res_empty_drift = calculate_cpa(
        [{"lat": 10.0, "lon": 70.0, "time": "2026-09-21T10:00:00Z"}],
        [],
    )
    assert res_empty_drift["cpa_score"] == 0.0

    # Vessel track < 2 points
    res_short_vessel = calculate_cpa(
        [{"lat": 10.0, "lon": 70.0, "time": "2026-09-21T10:00:00Z"}],
        [{"lat": 10.0, "lon": 70.0, "time": "2026-09-21T10:00:00Z"}],
    )
    assert res_short_vessel["cpa_score"] == 0.0
