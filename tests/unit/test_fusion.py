"""Unit tests for Multi-Factor Evidential Fusion."""

import pytest
from core.phase5_attribution.fusion import fuse_scores


def test_capacity_veto_returns_zero_immediately():
    """Test when Pillar 4 multiplier is 0.0, total_score and calibrated_score are 0.0 immediately."""
    pillar_results = {
        "pillar1_cpa": {"cpa_score": 1.0},
        "pillar2_dark": {"dark_vessel_score": 1.0},
        "pillar3_loiter": {"loitering_score": 0.4},
        "pillar4_capacity": {"multiplier": 0.0},  # VETO
        "pillar5_draft": {"draft_change_score": 0.8},
        "pillar6_permutation": {"p_value": 0.001},
        "pillar7_sensitivity": {"stability_index": 0.95},
    }
    res = fuse_scores(pillar_results)
    assert res["total_score"] == 0.0
    assert res["calibrated_score"] == 0.0
    assert "capacity_veto" in res["reason"]


def test_all_pillars_zero():
    """Test all pillars zero yields 0.0 total and calibrated scores."""
    pillar_results = {
        "pillar1_cpa": {"cpa_score": 0.0},
        "pillar2_dark": {"dark_vessel_score": 0.0},
        "pillar3_loiter": {"loitering_score": 0.0},
        "pillar4_capacity": {"multiplier": 1.0},
        "pillar5_draft": {"draft_change_score": 0.0},
        "pillar6_permutation": {"p_value": 1.0},
        "pillar7_sensitivity": {"stability_index": 0.0},
    }
    res = fuse_scores(pillar_results)
    assert res["total_score"] == 10.0  # Only capacity multiplier (weight 0.10 * 1.0 = 10.0)
    assert res["calibrated_score"] < 0.10


def test_strong_attribution_fusion():
    """Test high scoring suspect yields high total and calibrated scores."""
    pillar_results = {
        "pillar1_cpa": {"cpa_score": 0.95},
        "pillar2_dark": {"dark_vessel_score": 0.85},
        "pillar3_loiter": {"loitering_score": 0.40},
        "pillar4_capacity": {"multiplier": 1.0},
        "pillar5_draft": {"draft_change_score": 0.70},
        "pillar6_permutation": {"p_value": 0.001},
        "pillar7_sensitivity": {"stability_index": 0.94},
    }
    res = fuse_scores(pillar_results)
    assert res["total_score"] >= 75.0
    assert res["calibrated_score"] >= 0.80
    assert "cpa" in res["pillar_contributions"]


def test_custom_weights():
    """Test custom weights override defaults correctly."""
    pillar_results = {
        "pillar1_cpa": {"cpa_score": 1.0},
        "pillar4_capacity": {"multiplier": 1.0},
    }
    custom_weights = {"cpa": 0.80, "capacity": 0.20}
    res = fuse_scores(pillar_results, weights=custom_weights)
    assert res["total_score"] == 100.0


def test_empty_results_handling():
    """Test empty results dict returns zero score without crashing."""
    res = fuse_scores({})
    assert res["total_score"] == 0.0
    assert res["calibrated_score"] == 0.0
    assert "no_pillar_results" in res["reason"]
