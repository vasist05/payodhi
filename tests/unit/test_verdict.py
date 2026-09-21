"""Unit tests for 3-Tiered Legal Verdict Classification."""

import math
import pytest
from core.phase5_attribution.verdict import classify_verdict


def test_tier1_prosecutable():
    """Test Tier 1 PROSECUTABLE: p < 0.01, score >= 0.80, stability >= 0.90."""
    res = classify_verdict(calibrated_score=0.85, p_value=0.001, stability_index=0.94)
    assert res["verdict"] == "PROSECUTABLE"
    assert res["evidence_strength"] == "STRONG"
    assert "tier1_prosecutable" in res["reason"]


def test_tier2_person_of_interest():
    """Test Tier 2 PERSON_OF_INTEREST: p < 0.05, 0.60 <= score < 0.80."""
    res = classify_verdict(calibrated_score=0.68, p_value=0.03, stability_index=0.85)
    assert res["verdict"] == "PERSON_OF_INTEREST"
    assert res["evidence_strength"] == "MODERATE"
    assert "tier2_person_of_interest" in res["reason"]


def test_null_hypothesis_insufficient_evidence():
    """Test when p_value > 0.05, verdict is strictly INSUFFICIENT_EVIDENCE even with high score."""
    res = classify_verdict(calibrated_score=0.95, p_value=0.08, stability_index=0.95)
    assert res["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert res["evidence_strength"] == "WEAK"
    assert "H0_null_hypothesis_accepted" in res["reason"]


def test_edge_case_score_clamping():
    """Test scores > 1.0 or < 0.0 are clamped to [0.0, 1.0]."""
    res_high = classify_verdict(calibrated_score=1.5, p_value=0.001, stability_index=0.95)
    assert res_high["verdict"] == "PROSECUTABLE"
    assert "score_clamped_to_1.0" in res_high["reason"]

    res_low = classify_verdict(calibrated_score=-0.2, p_value=0.01, stability_index=0.90)
    assert res_low["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "score_clamped_to_0.0" in res_low["reason"]


def test_edge_case_nan_or_none_invalid_score():
    """Test NaN or None inputs return invalid_score."""
    res_nan = classify_verdict(calibrated_score=float("nan"), p_value=0.01, stability_index=0.90)
    assert res_nan["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "invalid_score" in res_nan["reason"]

    res_none = classify_verdict(calibrated_score=None, p_value=0.01, stability_index=0.90)
    assert res_none["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "invalid_score" in res_none["reason"]


def test_edge_case_capacity_veto_and_all_pillars_zero():
    """Test capacity veto context and all pillars zero return INSUFFICIENT_EVIDENCE."""
    res_veto = classify_verdict(0.0, 0.01, 0.90, reason_context="capacity_veto")
    assert res_veto["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "capacity_veto" in res_veto["reason"]

    res_zeros = classify_verdict(0.0, 0.01, 0.90, reason_context="all_pillars_zero")
    assert res_zeros["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "all_pillars_zero" in res_zeros["reason"]


def test_db_verdict_matches_database_enum():
    """Verify db_verdict field exactly matches backend VerdictEnum values."""
    res1 = classify_verdict(calibrated_score=0.85, p_value=0.001, stability_index=0.95)
    assert res1["db_verdict"] == "prosecutable"

    res2 = classify_verdict(calibrated_score=0.70, p_value=0.02, stability_index=0.85)
    assert res2["db_verdict"] == "person_of_interest"

    res3 = classify_verdict(calibrated_score=0.40, p_value=0.10, stability_index=0.50)
    assert res3["db_verdict"] == "insufficient_evidence"
