"""
backend/evidence_engine/evidence_builder.py
============================================
Phase 6 — Evidence & Explainability Layer

Takes the ranked AttributionResult list from Phase 5 and builds:
  1. For each vessel — a structured card with evidence bullets
     (what matched ✅, what weakened/disqualified ❌)
  2. A narrative sentence per vessel
  3. An overall EvidenceReport consumed by Phase 7 (Dashboard)

Design philosophy (applied XAI for high-stakes domain)
--------------------------------------------------------
- Every factor used in Phase 5 scoring is explained in plain English here
- Lower-ranked vessels get "why NOT" explanations — not just the winner
- The system explicitly acknowledges when it lacks sufficient evidence
- Language is deliberately investigative-neutral ("indicates", "warrants
  investigation") — not accusatory
"""

from __future__ import annotations
from typing import List

from backend.schemas import (
    AttributionResult, AttributionOutcome, DriftResult,
    EvidenceBullet, VesselEvidenceCard, EvidenceReport,
    HIGH_RISK_TYPES, HIGH_RISK_CARGO
)
from backend.attribution_engine.ranking import SEPARATION_GAP


# ---------------------------------------------------------------------------
# Bullet generators — one per scoring factor
# ---------------------------------------------------------------------------

def _drift_bullets(result: AttributionResult) -> List[EvidenceBullet]:
    bd = result.score_breakdown
    v = result.vessel
    bullets = []

    agreement = bd.drift_agreement_score
    if v.bidirectional_drift_agreement is not None:
        pct = int(agreement * 100)
        if agreement >= 0.75:
            bullets.append(EvidenceBullet(
                positive=True,
                text=f"Bidirectional drift agreement: {pct}% — forward drift from vessel "
                     f"trajectory closely matches detected spill location"
            ))
        elif agreement >= 0.45:
            bullets.append(EvidenceBullet(
                positive=False,
                text=f"Bidirectional drift agreement: {pct}% — partial match; "
                     f"vessel trajectory is moderately consistent with spill origin"
            ))
        else:
            bullets.append(EvidenceBullet(
                positive=False,
                text=f"Bidirectional drift agreement: {pct}% — vessel trajectory is "
                     f"inconsistent with estimated spill drift path"
            ))
    else:
        # Phase 3 bidirectional not yet run — distance proxy was used
        if agreement >= 0.6:
            bullets.append(EvidenceBullet(
                positive=True,
                text="Spatial proximity suggests vessel was within plausible drift origin "
                     "region (bidirectional check not yet available)"
            ))
        else:
            bullets.append(EvidenceBullet(
                positive=False,
                text="Vessel appears outside plausible drift origin region "
                     "(bidirectional check not yet available)"
            ))
    return bullets


def _time_bullets(result: AttributionResult) -> List[EvidenceBullet]:
    v = result.vessel
    bullets = []

    if v.ais_gap_minutes == 0:
        bullets.append(EvidenceBullet(
            positive=True,
            text="AIS signal continuous throughout critical window — no gaps detected"
        ))
    elif v.ais_gap_minutes <= 15:
        bullets.append(EvidenceBullet(
            positive=False,
            text=f"Minor AIS gap of {v.ais_gap_minutes} minutes during critical window — "
                 f"requires further investigation"
        ))
    else:
        bullets.append(EvidenceBullet(
            positive=False,
            text=f"AIS gap of {v.ais_gap_minutes} minutes during estimated release window — "
                 f"vessel position during this period is unverified"
        ))

    if v.speed_kts <= 6.0:
        bullets.append(EvidenceBullet(
            positive=True,
            text=f"Vessel speed {v.speed_kts:.1f} kts — slow transit consistent with "
                 f"prolonged time in origin area during release window"
        ))
    elif v.speed_kts >= 10.0:
        bullets.append(EvidenceBullet(
            positive=False,
            text=f"Vessel speed {v.speed_kts:.1f} kts — fast transit suggests limited "
                 f"time in origin area during release window"
        ))

    return bullets


def _spatial_bullets(result: AttributionResult) -> List[EvidenceBullet]:
    v = result.vessel
    dist = v.distance_from_origin_km
    bullets = []

    if dist <= 3.5:
        bullets.append(EvidenceBullet(
            positive=True,
            text=f"Vessel was {dist:.1f} km from estimated spill origin — "
                 f"within high-probability release zone"
        ))
    elif dist <= 8.0:
        bullets.append(EvidenceBullet(
            positive=False,
            text=f"Vessel was {dist:.1f} km from estimated spill origin — "
                 f"within possible release zone but not in highest-probability region"
        ))
    else:
        bullets.append(EvidenceBullet(
            positive=False,
            text=f"Vessel was {dist:.1f} km from estimated spill origin — "
                 f"outside the high-probability release zone"
        ))

    # Heading consistency (basic check — heading toward/away from origin)
    h = v.heading_deg
    # Rough heuristic: southward headings (135–270) match most Indian coastal spill patterns in our AOIs
    # Phase 3 owner can replace this with a proper heading-vs-drift-vector comparison
    if 135 <= h <= 270:
        bullets.append(EvidenceBullet(
            positive=True,
            text=f"Vessel heading {h:.0f}° — direction consistent with southward coastal transit "
                 f"near origin area"
        ))
    else:
        bullets.append(EvidenceBullet(
            positive=False,
            text=f"Vessel heading {h:.0f}° — direction appears inconsistent with "
                 f"the estimated drift and release geometry"
        ))

    return bullets


def _vessel_characteristic_bullets(result: AttributionResult) -> List[EvidenceBullet]:
    v = result.vessel
    bullets = []

    type_lower = v.type.lower()
    is_high_risk = type_lower in HIGH_RISK_TYPES or any(k in type_lower for k in ("tanker", "chemical", "bunker"))
    if is_high_risk:
        bullets.append(EvidenceBullet(
            positive=True,
            text=f"Vessel type: {v.type} — consistent with a realistic source of oil pollution"
        ))
    else:
        bullets.append(EvidenceBullet(
            positive=False,
            text=f"Vessel type: {v.type} — not typically associated with oil pollution events"
        ))

    if v.cargo_history:
        cargo_lower = [c.lower() for c in v.cargo_history]
        risky = [c for c in cargo_lower if c in HIGH_RISK_CARGO]
        if risky:
            bullets.append(EvidenceBullet(
                positive=True,
                text=f"Recent cargo history includes high-risk petroleum products: "
                     f"{', '.join(v.cargo_history)}"
            ))
        else:
            bullets.append(EvidenceBullet(
                positive=False,
                text=f"Recent cargo history does not indicate petroleum products: "
                     f"{', '.join(v.cargo_history)}"
            ))
    else:
        bullets.append(EvidenceBullet(
            positive=False,
            text="No cargo history available — risk profile based on vessel type only"
        ))

    return bullets


def _behavioral_bullets(result: AttributionResult) -> List[EvidenceBullet]:
    v = result.vessel
    bullets = []

    if v.dark_vessel:
        bullets.append(EvidenceBullet(
            positive=False,
            text="⚠️ Vessel appears in SAR imagery but NOT in AIS records — "
                 "classified as AIS-invisible; warrants further investigation"
        ))

    score = v.behavioral_anomaly_score
    if score >= 70:
        bullets.append(EvidenceBullet(
            positive=False,
            text=f"Behavioral anomaly score: {score:.0f}/100 — significant anomalies detected "
                 f"(speed changes, course deviations, or AIS irregularities)"
        ))
    elif score >= 40:
        bullets.append(EvidenceBullet(
            positive=False,
            text=f"Behavioral anomaly score: {score:.0f}/100 — moderate anomalies detected"
        ))
    else:
        bullets.append(EvidenceBullet(
            positive=True,
            text=f"Behavioral anomaly score: {score:.0f}/100 — no significant anomalies detected "
                 f"(normal operational behavior observed)"
        ))

    return bullets


# ---------------------------------------------------------------------------
# Narrative generator
# ---------------------------------------------------------------------------

def _build_narrative(result: AttributionResult, outcome: AttributionOutcome) -> str:
    v = result.vessel
    score = result.attribution_score
    dist = v.distance_from_origin_km

    if result.rank == 1:
        if outcome == AttributionOutcome.STRONG:
            return (
                f"Most probable source: {v.name} (MMSI {v.mmsi}) — "
                f"Attribution Score {score:.0f}/100 (Strong) — "
                f"Key evidence: {dist:.1f} km from origin, "
                f"{v.type} with petroleum cargo history, "
                f"{int(result.score_breakdown.drift_agreement_score * 100)}% drift agreement."
            )
        elif outcome == AttributionOutcome.INCONCLUSIVE:
            return (
                f"Highest-scoring candidate: {v.name} (MMSI {v.mmsi}) — "
                f"Attribution Score {score:.0f}/100 — "
                f"Result is inconclusive; multiple vessels have similar scores. "
                f"Additional investigation recommended."
            )
        else:
            return (
                f"Insufficient evidence to attribute spill to any single vessel. "
                f"Highest-scoring candidate: {v.name} — Score {score:.0f}/100. "
                f"Broader investigation required."
            )
    else:
        return (
            f"Lower-ranked candidate: {v.name} (MMSI {v.mmsi}) — "
            f"Attribution Score {score:.0f}/100 — "
            f"{dist:.1f} km from origin; "
            f"ranked below primary candidate due to weaker evidence alignment."
        )


# ---------------------------------------------------------------------------
# Main Phase 6 entry point
# ---------------------------------------------------------------------------

def build_evidence_report(
    ranked_results: List[AttributionResult],
    outcome: AttributionOutcome,
    drift: DriftResult,
    incident_id: str = "INC-UNKNOWN"
) -> EvidenceReport:
    """
    Main Phase 6 entry point.

    Parameters
    ----------
    ranked_results : List[AttributionResult]
        Output of Phase 5 rank_vessels(), sorted by score descending.
    outcome : AttributionOutcome
        Overall outcome from Phase 5.
    drift : DriftResult
        Phase 3 drift result (used for context in report header).
    incident_id : str
        Identifier for this spill event (from incident tracking system).

    Returns
    -------
    EvidenceReport
        Full structured report consumed by Phase 7 (Dashboard / PDF).
    """
    cards: List[VesselEvidenceCard] = []

    for result in ranked_results:
        bullets: List[EvidenceBullet] = []
        bullets.extend(_drift_bullets(result))
        bullets.extend(_time_bullets(result))
        bullets.extend(_spatial_bullets(result))
        bullets.extend(_vessel_characteristic_bullets(result))
        bullets.extend(_behavioral_bullets(result))

        narrative = _build_narrative(result, outcome)

        outcome_label_map = {
            AttributionOutcome.STRONG:       "Strong",
            AttributionOutcome.INCONCLUSIVE: "Inconclusive",
            AttributionOutcome.INSUFFICIENT: "Insufficient Evidence",
        }
        outcome_label = outcome_label_map[outcome] if result.rank == 1 else "Candidate"

        cards.append(VesselEvidenceCard(
            vessel_name=result.vessel.name,
            mmsi=result.vessel.mmsi,
            rank=result.rank,
            attribution_score=result.attribution_score,
            outcome_label=outcome_label,
            bullets=bullets,
            narrative=narrative,
        ))

    # Primary summary
    if not ranked_results:
        primary_summary = "No candidate vessels identified. Investigation cannot proceed."
    elif outcome == AttributionOutcome.STRONG:
        top = ranked_results[0]
        primary_summary = (
            f"Strong attribution: {top.vessel.name} (Score {top.attribution_score:.0f}/100). "
            f"{len(ranked_results)} candidates evaluated. "
            f"This vessel's spatial, temporal, and drift evidence is significantly stronger "
            f"than any alternative candidate."
        )
    elif outcome == AttributionOutcome.INCONCLUSIVE:
        primary_summary = (
            f"{len(ranked_results)} candidates evaluated. Evidence is inconclusive — "
            f"multiple vessels score within {SEPARATION_GAP:.0f} points of each other. "
            f"Recommend further investigation before attribution."
        )
    else:
        primary_summary = (
            f"{len(ranked_results)} candidates evaluated. No vessel meets the minimum "
            f"attribution threshold. Insufficient evidence to identify a probable source. "
            f"Recommend expanding the search window or obtaining additional data."
        )

    return EvidenceReport(
        incident_id=incident_id,
        spill_detected_utc=drift.spill_detected_utc,
        overall_outcome=outcome,
        primary_summary=primary_summary,
        cards=cards,
        total_candidates_evaluated=len(ranked_results),
        model_version="5.6-live",  # Ennore: real GFW AIS data; Haldia/Mumbai: validated mock data
    )
