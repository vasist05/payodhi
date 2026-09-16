"""
backend/attribution_engine/ranking.py
======================================
Phase 5 — Attribution Ranking Engine

Implements the multi-factor weighted scoring formula from the SIH26143 plan:

    Attribution Score =
        0.35 × drift_agreement_score
      + 0.25 × time_overlap_score
      + 0.20 × spatial_proximity_score
      + 0.10 × vessel_characteristics_score
      + 0.10 × behavioral_anomaly_score

Produces a ranked list of AttributionResult objects and an overall
AttributionOutcome (STRONG / INCONCLUSIVE / INSUFFICIENT).

Design notes
------------
- All sub-scores are normalized to 0.0–1.0 before weighting
- The final "Attribution Score" is reported as 0–100 (× 100)
- Weights sum to exactly 1.0 (validated in tests)
- The three-outcome logic is intentionally conservative — a system
  that says "inconclusive" when the evidence is ambiguous is more
  credible than one that always forces a verdict
"""

from __future__ import annotations
from datetime import datetime
import math
from typing import List, Tuple

from backend.schemas import (
    CandidateVessel, DriftResult,
    AttributionResult, AttributionOutcome, ScoreBreakdown,
    HIGH_RISK_TYPES, HIGH_RISK_CARGO
)


# ---------------------------------------------------------------------------
# Scoring weights — adjust here after Phase 8 validation
# ---------------------------------------------------------------------------

WEIGHTS = {
    "drift_agreement":       0.35,
    "time_overlap":          0.25,
    "spatial_proximity":     0.20,
    "vessel_characteristics": 0.10,
    "behavioral_anomaly":    0.10,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


# ---------------------------------------------------------------------------
# Outcome thresholds
# ---------------------------------------------------------------------------

STRONG_THRESHOLD    = 65.0   # top vessel must score ≥ this
SEPARATION_GAP      = 20.0   # top vessel must be ≥ this many points ahead of #2
INSUFFICIENT_CUTOFF = 30.0   # if top vessel scores below this → INSUFFICIENT


# ---------------------------------------------------------------------------
# Sub-score calculators
# ---------------------------------------------------------------------------

def _drift_agreement_score(vessel: CandidateVessel) -> float:
    """
    0.0–1.0 — based on Phase 3 bidirectional drift check.
    If Phase 3 hasn't run the bidirectional check yet (None),
    falls back to a distance-based proxy so Phase 5 still works.
    """
    if vessel.bidirectional_drift_agreement is not None:
        return float(vessel.bidirectional_drift_agreement)
    # Proxy: closer vessel → higher assumed agreement (normalized at 20 km)
    return max(0.0, 1.0 - vessel.distance_from_origin_km / 20.0)


def _time_overlap_score(vessel: CandidateVessel, drift: DriftResult) -> float:
    if vessel.position_timestamp_utc is not None:
        ts = datetime.fromisoformat(vessel.position_timestamp_utc.replace("Z", "+00:00"))
        start = datetime.fromisoformat(drift.origin_window.start_utc.replace("Z", "+00:00"))
        end = datetime.fromisoformat(drift.origin_window.end_utc.replace("Z", "+00:00"))
        if start <= ts <= end:
            return 1.0
        # outside window — decay score by how far outside (in minutes)
        minutes_outside = min(abs((ts - start).total_seconds()), abs((ts - end).total_seconds())) / 60.0
        return max(0.0, 1.0 - minutes_outside / 60.0)
    # Fallback proxy (used until Phase 4 provides timestamps)
    gap_penalty = min(vessel.ais_gap_minutes / 60.0, 1.0)
    speed_bonus = max(0.0, 1.0 - vessel.speed_kts / 20.0)
    base = (1.0 - gap_penalty * 0.4) * 0.6 + speed_bonus * 0.4
    return min(1.0, max(0.0, base))


def _spatial_proximity_score(vessel: CandidateVessel) -> float:
    """
    0.0–1.0 — distance from Phase 3 origin centroid.
    Uses exponential decay: score ~1.0 at 0 km, ~0.5 at 5 km,
    ~0.13 at 15 km, ~0.0 beyond 25 km.
    """
    return math.exp(-vessel.distance_from_origin_km / 7.5)


def _vessel_characteristics_score(vessel: CandidateVessel) -> float:
    """
    0.0–1.0 — vessel type and cargo history.
    Justified by maritime risk-profiling literature:
    tankers/chemical carriers are the realistic sources of oil pollution.

    Score composition:
      0.6 — vessel type risk
      0.4 — cargo history risk (adjusted per actual recent cargo)
    """
    type_lower = vessel.type.lower()
    is_high_risk = type_lower in HIGH_RISK_TYPES or any(k in type_lower for k in ("tanker", "chemical", "bunker"))
    type_score = 1.0 if is_high_risk else 0.2

    if vessel.cargo_history:
        cargo_lower = [c.lower() for c in vessel.cargo_history]
        high_risk_count = sum(1 for c in cargo_lower if c in HIGH_RISK_CARGO)
        cargo_score = min(1.0, high_risk_count / max(1, len(cargo_lower)))
    else:
        cargo_score = 0.0  # unknown cargo → no bonus

    return 0.6 * type_score + 0.4 * cargo_score


def _behavioral_anomaly_score(vessel: CandidateVessel) -> float:
    """
    0.0–1.0 — directly from Phase 4's behavioral anomaly score (0–100).
    Dark vessel flag adds a fixed bonus (flagged for further investigation).
    """
    base = vessel.behavioral_anomaly_score / 100.0
    dark_bonus = 0.15 if vessel.dark_vessel else 0.0
    return min(1.0, base + dark_bonus)


# ---------------------------------------------------------------------------
# Main ranking function
# ---------------------------------------------------------------------------

def compute_attribution_score(
    vessel: CandidateVessel,
    drift: DriftResult
) -> ScoreBreakdown:
    """Compute all sub-scores and weighted total for one vessel."""
    s = {
        "drift_agreement":       _drift_agreement_score(vessel),
        "time_overlap":          _time_overlap_score(vessel, drift),
        "spatial_proximity":     _spatial_proximity_score(vessel),
        "vessel_characteristics": _vessel_characteristics_score(vessel),
        "behavioral_anomaly":    _behavioral_anomaly_score(vessel),
    }

    weighted_total = sum(s[k] * WEIGHTS[k] for k in WEIGHTS) * 100.0

    return ScoreBreakdown(
        drift_agreement_score=round(s["drift_agreement"], 4),
        time_overlap_score=round(s["time_overlap"], 4),
        spatial_proximity_score=round(s["spatial_proximity"], 4),
        vessel_characteristics_score=round(s["vessel_characteristics"], 4),
        behavioral_anomaly_score=round(s["behavioral_anomaly"], 4),
        weighted_total=round(weighted_total, 2),
    )


def determine_outcome(ranked: List[AttributionResult]) -> AttributionOutcome:
    """
    Determine overall outcome from the ranked list.

    STRONG        → #1 scores ≥ STRONG_THRESHOLD AND is ≥ SEPARATION_GAP above #2
    INSUFFICIENT  → #1 scores < INSUFFICIENT_CUTOFF
    INCONCLUSIVE  → everything else (multiple vessels score similarly)
    """
    if not ranked:
        return AttributionOutcome.INSUFFICIENT

    top_score = ranked[0].attribution_score

    if top_score < INSUFFICIENT_CUTOFF:
        return AttributionOutcome.INSUFFICIENT

    if len(ranked) >= 2:
        second_score = ranked[1].attribution_score
        gap = top_score - second_score
        if top_score >= STRONG_THRESHOLD and gap >= SEPARATION_GAP:
            return AttributionOutcome.STRONG
        return AttributionOutcome.INCONCLUSIVE

    # Only one candidate — if it meets threshold, it's strong
    if top_score >= STRONG_THRESHOLD:
        return AttributionOutcome.STRONG
    return AttributionOutcome.INCONCLUSIVE


def rank_vessels(
    candidates: List[CandidateVessel],
    drift: DriftResult
) -> Tuple[List[AttributionResult], AttributionOutcome]:
    """
    Main Phase 5 entry point.

    Parameters
    ----------
    candidates : List[CandidateVessel]
        Candidate vessels from Phase 4 (or mock_data.py during development).
    drift : DriftResult
        Drift reconstruction output from Phase 3.

    Returns
    -------
    ranked_results : List[AttributionResult]
        Vessels sorted by attribution_score descending, with rank assigned.
    outcome : AttributionOutcome
        STRONG / INCONCLUSIVE / INSUFFICIENT for the overall result.
    """
    scored: List[Tuple[float, CandidateVessel, ScoreBreakdown]] = []

    for vessel in candidates:
        breakdown = compute_attribution_score(vessel, drift)
        scored.append((breakdown.weighted_total, vessel, breakdown))

    scored.sort(key=lambda x: x[0], reverse=True)

    ranked_results: List[AttributionResult] = []
    for rank_idx, (score, vessel, breakdown) in enumerate(scored, start=1):
        ranked_results.append(AttributionResult(
            rank=rank_idx,
            vessel=vessel,
            attribution_score=score,
            score_breakdown=breakdown,
            outcome=AttributionOutcome.STRONG,  # placeholder; overwritten below
        ))

    outcome = determine_outcome(ranked_results)

    # Stamp the overall outcome on every result (consumers expect it)
    for result in ranked_results:
        result.outcome = outcome

    return ranked_results, outcome
