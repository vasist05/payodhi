"""
backend/attribution_engine/tests/test_ranking.py
Unit tests for Phase 5 — Attribution Ranking Engine
"""

import pytest
from backend.attribution_engine.ranking import (
    rank_vessels, compute_attribution_score, determine_outcome,
    WEIGHTS, STRONG_THRESHOLD, SEPARATION_GAP, INSUFFICIENT_CUTOFF
)
from backend.attribution_engine.mock_data import get_mock_inputs
from backend.schemas import (
    CandidateVessel, DriftResult, OriginWindow,
    AttributionOutcome, AttributionResult
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_inputs():
    return get_mock_inputs()


@pytest.fixture
def ranked(mock_inputs):
    drift, vessels = mock_inputs
    results, outcome = rank_vessels(vessels, drift)
    return results, outcome


# ---------------------------------------------------------------------------
# Weight sanity
# ---------------------------------------------------------------------------

def test_weights_sum_to_one():
    """Critical: weights must sum to exactly 1.0 — checked at import time too."""
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_all_weight_keys_present():
    expected = {"drift_agreement", "time_overlap", "spatial_proximity",
                "vessel_characteristics", "behavioral_anomaly"}
    assert set(WEIGHTS.keys()) == expected


# ---------------------------------------------------------------------------
# Ranking correctness
# ---------------------------------------------------------------------------

def test_rank_order(ranked):
    results, _ = ranked
    scores = [r.attribution_score for r in results]
    assert scores == sorted(scores, reverse=True), "Results must be sorted descending"


def test_rank_numbers(ranked):
    results, _ = ranked
    for i, r in enumerate(results, start=1):
        assert r.rank == i, f"Rank mismatch at index {i}"


def test_clear_winner_is_sagar_samrat(ranked):
    """The mock data is designed so MV SAGAR SAMRAT ranks #1."""
    results, _ = ranked
    assert results[0].vessel.mmsi == "419001234", (
        "MV SAGAR SAMRAT (MMSI 419001234) should rank #1 in mock scenario"
    )


def test_loser_is_last(ranked):
    """MV ATLANTIC BRIDGE is 18 km away — should rank last."""
    results, _ = ranked
    assert results[-1].vessel.mmsi == "636012345", (
        "MV ATLANTIC BRIDGE (MMSI 636012345) should rank last"
    )


def test_scores_in_valid_range(ranked):
    results, _ = ranked
    for r in results:
        assert 0.0 <= r.attribution_score <= 100.0, (
            f"{r.vessel.name} score {r.attribution_score} out of 0-100 range"
        )


def test_score_breakdown_fields(ranked):
    results, _ = ranked
    for r in results:
        bd = r.score_breakdown
        for field_name in [
            "drift_agreement_score", "time_overlap_score",
            "spatial_proximity_score", "vessel_characteristics_score",
            "behavioral_anomaly_score"
        ]:
            val = getattr(bd, field_name)
            assert 0.0 <= val <= 1.0, (
                f"{r.vessel.name}.{field_name} = {val} is out of 0-1 range"
            )


def test_outcome_is_strong_for_mock(ranked):
    """Mock data has a clear winner — outcome should be STRONG."""
    _, outcome = ranked
    assert outcome == AttributionOutcome.STRONG


def test_outcome_stamped_on_all_results(ranked):
    results, outcome = ranked
    for r in results:
        assert r.outcome == outcome, (
            f"Outcome not stamped correctly on {r.vessel.name}"
        )


# ---------------------------------------------------------------------------
# Three-outcome logic edge cases
# ---------------------------------------------------------------------------

def test_insufficient_outcome_when_all_scores_low():
    """If all vessels are far away and generic cargo, score should be too low."""
    drift, _ = get_mock_inputs()
    low_vessels = [
        CandidateVessel(
            mmsi="000000001", name="MV FAR AWAY", type="General cargo", flag="XX",
            position_lat=22.5, position_lon=88.8,
            distance_from_origin_km=35.0,
            heading_deg=90, speed_kts=12.0,
            ais_gap_minutes=0, dark_vessel=False,
            behavioral_anomaly_score=5.0,
            cargo_history=["sand"],
            bidirectional_drift_agreement=0.05
        )
    ]
    results, outcome = rank_vessels(low_vessels, drift)
    assert outcome == AttributionOutcome.INSUFFICIENT


def test_inconclusive_when_vessels_score_similarly():
    """If two vessels have identical profiles, outcome should be INCONCLUSIVE."""
    drift, _ = get_mock_inputs()
    twin_vessel = CandidateVessel(
        mmsi="111111111", name="MV TWIN A", type="Oil tanker", flag="IN",
        position_lat=21.965, position_lon=88.085,
        distance_from_origin_km=3.0,
        heading_deg=215, speed_kts=5.0,
        ais_gap_minutes=10, dark_vessel=False,
        behavioral_anomaly_score=60.0,
        cargo_history=["crude oil"],
        bidirectional_drift_agreement=0.75
    )
    twin_vessel_2 = CandidateVessel(
        mmsi="222222222", name="MV TWIN B", type="Oil tanker", flag="IN",
        position_lat=21.965, position_lon=88.085,
        distance_from_origin_km=3.0,
        heading_deg=215, speed_kts=5.0,
        ais_gap_minutes=10, dark_vessel=False,
        behavioral_anomaly_score=60.0,
        cargo_history=["crude oil"],
        bidirectional_drift_agreement=0.75
    )
    results, outcome = rank_vessels([twin_vessel, twin_vessel_2], drift)
    assert outcome == AttributionOutcome.INCONCLUSIVE


# ---------------------------------------------------------------------------
# No-candidate edge case
# ---------------------------------------------------------------------------

def test_empty_candidate_list():
    drift, _ = get_mock_inputs()
    results, outcome = rank_vessels([], drift)
    assert results == []
    assert outcome == AttributionOutcome.INSUFFICIENT


# ---------------------------------------------------------------------------
# Drift agreement fallback (bidirectional_drift_agreement = None)
# ---------------------------------------------------------------------------

def test_none_drift_agreement_uses_distance_proxy():
    """If Phase 3 bidirectional check hasn't run, proximity proxy is used."""
    drift, _ = get_mock_inputs()
    v = CandidateVessel(
        mmsi="999999999", name="MV NO DRIFT", type="Oil tanker", flag="IN",
        position_lat=21.97, position_lon=88.09,
        distance_from_origin_km=2.0,
        heading_deg=200, speed_kts=5.0,
        ais_gap_minutes=0, dark_vessel=False,
        behavioral_anomaly_score=50.0,
        cargo_history=["crude oil"],
        bidirectional_drift_agreement=None   # <-- Phase 3 not yet done
    )
    breakdown = compute_attribution_score(v, drift)
    # Should still produce a valid score without crashing
    assert 0.0 <= breakdown.weighted_total <= 100.0
