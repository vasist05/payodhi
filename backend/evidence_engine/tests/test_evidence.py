"""
backend/evidence_engine/tests/test_evidence.py
Unit tests for Phase 6 — Evidence & Explainability Layer
"""

import pytest
from backend.attribution_engine.mock_data import get_mock_inputs
from backend.attribution_engine.ranking import rank_vessels
from backend.evidence_engine.evidence_builder import build_evidence_report
from backend.schemas import (
    AttributionOutcome, EvidenceReport, VesselEvidenceCard, EvidenceBullet
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_report():
    drift, vessels = get_mock_inputs()
    ranked, outcome = rank_vessels(vessels, drift)
    return build_evidence_report(
        ranked, outcome, drift, incident_id="INC-TEST-001"
    )


# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------

def test_report_has_correct_incident_id(full_report):
    assert full_report.incident_id == "INC-TEST-001"


def test_report_candidate_count(full_report):
    """Should have 4 cards (one per mock vessel)."""
    assert full_report.total_candidates_evaluated == 4
    assert len(full_report.cards) == 4


def test_cards_sorted_by_rank(full_report):
    ranks = [c.rank for c in full_report.cards]
    assert ranks == sorted(ranks), "Cards must be in ascending rank order"


def test_each_card_has_mmsi(full_report):
    for card in full_report.cards:
        assert card.mmsi, f"Card for {card.vessel_name} is missing MMSI"


def test_attribution_scores_in_range(full_report):
    for card in full_report.cards:
        assert 0.0 <= card.attribution_score <= 100.0, (
            f"{card.vessel_name} score {card.attribution_score} out of range"
        )


# ---------------------------------------------------------------------------
# Bullet quality
# ---------------------------------------------------------------------------

def test_every_card_has_bullets(full_report):
    for card in full_report.cards:
        assert len(card.bullets) > 0, f"{card.vessel_name} has no evidence bullets"


def test_bullets_have_text(full_report):
    for card in full_report.cards:
        for b in card.bullets:
            assert isinstance(b.text, str) and len(b.text) > 5, (
                f"Empty or invalid bullet in {card.vessel_name}"
            )


def test_winner_has_more_positive_bullets(full_report):
    """The #1 ranked vessel should have more positive than negative bullets."""
    winner = full_report.cards[0]
    positives = sum(1 for b in winner.bullets if b.positive)
    negatives = sum(1 for b in winner.bullets if not b.positive)
    assert positives >= negatives, (
        f"Winner {winner.vessel_name} has more negative bullets than positive: "
        f"{positives} positive, {negatives} negative"
    )


def test_last_ranked_has_more_negative_bullets(full_report):
    """The last-ranked vessel should have more negative than positive bullets."""
    loser = full_report.cards[-1]
    positives = sum(1 for b in loser.bullets if b.positive)
    negatives = sum(1 for b in loser.bullets if not b.positive)
    assert negatives >= positives, (
        f"Last-ranked {loser.vessel_name} should have more negative bullets"
    )


# ---------------------------------------------------------------------------
# Narrative and disclaimer
# ---------------------------------------------------------------------------

def test_all_cards_have_narrative(full_report):
    for card in full_report.cards:
        assert card.narrative and len(card.narrative) > 10, (
            f"Missing or trivial narrative for {card.vessel_name}"
        )


def test_all_cards_have_disclaimer(full_report):
    for card in full_report.cards:
        assert "legal determination" in card.disclaimer.lower(), (
            f"{card.vessel_name} disclaimer is missing legal-neutrality language"
        )


def test_primary_summary_populated(full_report):
    assert full_report.primary_summary and len(full_report.primary_summary) > 20


# ---------------------------------------------------------------------------
# Outcome label
# ---------------------------------------------------------------------------

def test_winner_outcome_label_for_strong(full_report):
    """With mock data, outcome should be STRONG → winner label should say 'Strong'."""
    winner = full_report.cards[0]
    assert full_report.overall_outcome == AttributionOutcome.STRONG
    assert "Strong" in winner.outcome_label


def test_non_winner_outcome_label(full_report):
    for card in full_report.cards[1:]:
        assert card.outcome_label == "Candidate", (
            f"Non-winner {card.vessel_name} should have outcome_label 'Candidate'"
        )


# ---------------------------------------------------------------------------
# Integration: full pipeline
# ---------------------------------------------------------------------------

def test_full_pipeline_runs_without_error():
    """Smoke test — full Phase 5 → 6 pipeline with mock data."""
    from backend.run_attribution import run_full_pipeline
    report = run_full_pipeline(use_real_data=False)
    assert isinstance(report, EvidenceReport)
    assert report.total_candidates_evaluated > 0
    assert report.overall_outcome in list(AttributionOutcome)


def test_full_pipeline_json_serializable():
    """Output must be JSON-serializable for Phase 7 API."""
    import json
    import dataclasses
    from backend.run_attribution import run_full_pipeline
    report = run_full_pipeline(use_real_data=False)
    try:
        json.dumps(dataclasses.asdict(report))
    except TypeError as e:
        pytest.fail(f"EvidenceReport is not JSON-serializable: {e}")
