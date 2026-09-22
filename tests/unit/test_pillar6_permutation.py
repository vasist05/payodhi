"""Unit tests for Pillar 6: Null Permutation Test."""

import pytest
from core.phase5_attribution.pillar6_permutation import permutation_test


def test_statistically_significant_candidate():
    """Test top vessel with high score against low background yields p < 0.05."""
    scores = {
        "vessel_suspect": 0.87,
        "vessel_b": 0.35,
        "vessel_c": 0.20,
        "vessel_d": 0.15,
        "vessel_e": 0.10,
    }
    res = permutation_test(scores, n_permutations=1000, seed=42)
    assert res["top_vessel_id"] == "vessel_suspect"
    assert res["top_score"] == 0.87
    assert res["p_value"] < 0.05
    assert res["baseline_99th"] < 0.87
    assert "statistically_significant" in res["reason"]


def test_edge_case_single_vessel():
    """Edge case 1: Only 1 vessel returns p_value=0.5 and single_suspect."""
    scores = {"vessel_lonely": 0.75}
    res = permutation_test(scores)
    assert res["p_value"] == 0.5
    assert res["top_vessel_id"] == "vessel_lonely"
    assert "single_suspect" in res["reason"]


def test_edge_case_all_scores_identical():
    """Edge case 2: All scores identical returns p_value=1.0."""
    scores = {"vessel_1": 0.60, "vessel_2": 0.60, "vessel_3": 0.60}
    res = permutation_test(scores)
    assert res["p_value"] == 1.0
    assert "all_scores_identical" in res["reason"]


def test_edge_case_all_scores_low():
    """Edge case 3: Top score < 0.3 returns p_value=1.0 and all_scores_low."""
    scores = {"vessel_1": 0.25, "vessel_2": 0.20, "vessel_3": 0.15}
    res = permutation_test(scores)
    assert res["p_value"] == 1.0
    assert "all_scores_low" in res["reason"]


def test_edge_case_empty_dict():
    """Edge case 4: Empty dict returns p_value=1.0 and no_vessels."""
    res = permutation_test({})
    assert res["p_value"] == 1.0
    assert res["reason"] == "no_vessels"


def test_borderline_non_significant_flags_insufficient_evidence():
    """Test when top vessel is close to or tied with background, p > 0.05 flags INSUFFICIENT_EVIDENCE."""
    scores = {
        "vessel_a": 0.40,
        "vessel_b": 0.40,  # Tied
        "vessel_c": 0.38,
    }
    res = permutation_test(scores, n_permutations=500, seed=42)
    assert res["p_value"] > 0.05
    assert "INSUFFICIENT_EVIDENCE" in res["reason"]


def test_reproducibility_with_seed():
    """Test that specifying seed yields identical p_value and baseline."""
    scores = {
        "vessel_top": 0.80,
        "vessel_2": 0.50,
        "vessel_3": 0.40,
        "vessel_4": 0.30,
    }
    res1 = permutation_test(scores, n_permutations=1000, seed=42)
    res2 = permutation_test(scores, n_permutations=1000, seed=42)
    assert res1["p_value"] == res2["p_value"]
    assert res1["baseline_99th"] == res2["baseline_99th"]
