"""Legal & Court Admissibility Layer: 3-Tiered Verdict Classification.

Categorizes forensic evidence into legally defensible tiers under UNCLOS / MARPOL:
- Tier 1 PROSECUTABLE: p_value < 0.01 AND calibrated_score >= 0.80 AND stability_index >= 0.90
- Tier 2 PERSON_OF_INTEREST: p_value < 0.05 AND 0.60 <= calibrated_score < 0.80
- Tier 3 INSUFFICIENT_EVIDENCE: All other conditions (or if p_value > 0.05, enforcing Null Hypothesis H0)

Edge cases handled:
1. calibrated_score > 1.0 -> clamp to 1.0, note in reason
2. calibrated_score < 0.0 -> clamp to 0.0, note in reason
3. NaN or None -> return INSUFFICIENT_EVIDENCE with "invalid_score"
4. All pillars 0.0 -> INSUFFICIENT_EVIDENCE with "all_pillars_zero"
5. Capacity veto -> INSUFFICIENT_EVIDENCE with "capacity_veto"
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional


def classify_verdict(
    calibrated_score: Optional[float],
    p_value: Optional[float],
    stability_index: Optional[float],
    reason_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Classify attribution results into a court-admissible 3-tiered verdict.

    Args:
        calibrated_score: Platt-calibrated probability [0.0 - 1.0].
        p_value: Empirical p-value from Pillar 6 permutation test.
        stability_index: Weather perturbation stability index from Pillar 7 [0.0 - 1.0].
        reason_context: Optional contextual notes (e.g. 'capacity_veto', 'all_pillars_zero').

    Returns:
        dict:
            verdict (str): 'PROSECUTABLE', 'PERSON_OF_INTEREST', or 'INSUFFICIENT_EVIDENCE'.
            reason (str): Explanatory reason detailing threshold evaluations.
            evidence_strength (str): 'STRONG', 'MODERATE', or 'WEAK'.
    """
    ctx = (reason_context or "").lower()

    # Edge case 5: Capacity veto
    if "capacity_veto" in ctx:
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reason": "capacity_veto (vessel capacity physically insufficient)",
            "evidence_strength": "NONE",
        }

    # Edge case 4: All pillars 0.0
    if "all_pillars_zero" in ctx or (calibrated_score == 0.0 and p_value is None):
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reason": "all_pillars_zero (no incriminating anomalies detected)",
            "evidence_strength": "NONE",
        }

    # Edge case 3: NaN or None in any metric
    if (
        calibrated_score is None
        or p_value is None
        or stability_index is None
        or math.isnan(calibrated_score)
        or math.isnan(p_value)
        or math.isnan(stability_index)
    ):
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reason": "invalid_score (missing or NaN metrics)",
            "evidence_strength": "NONE",
        }

    reason_flags = []

    # Edge case 1 & 2: Clamp calibrated_score to [0.0, 1.0]
    score = float(calibrated_score)
    if score > 1.0:
        score = 1.0
        reason_flags.append("score_clamped_to_1.0")
    elif score < 0.0:
        score = 0.0
        reason_flags.append("score_clamped_to_0.0")

    p = float(p_value)
    stab = float(stability_index)

    # Null Hypothesis Enforcement: If p > 0.05, strictly INSUFFICIENT_EVIDENCE
    if p > 0.05:
        reason_str = f"H0_null_hypothesis_accepted (p={p:.4f} > 0.05)"
        if reason_flags:
            reason_str += f" [{'; '.join(reason_flags)}]"
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reason": reason_str,
            "evidence_strength": "WEAK",
        }

    # Tier 1: PROSECUTABLE
    # Criteria: p < 0.01 AND calibrated_score >= 0.80 AND stability_index >= 0.90
    if p < 0.01 and score >= 0.80 and stab >= 0.90:
        reason_str = (
            f"tier1_prosecutable (score={score:.4f} >= 0.80, "
            f"p={p:.4f} < 0.01, stability={stab:.1%} >= 90%)"
        )
        if reason_flags:
            reason_str += f" [{'; '.join(reason_flags)}]"
        return {
            "verdict": "PROSECUTABLE",
            "reason": reason_str,
            "evidence_strength": "STRONG",
        }

    # Tier 2: PERSON_OF_INTEREST
    # Criteria: p < 0.05 AND 0.60 <= calibrated_score < 0.80 (or score >= 0.60 with borderline p/stability)
    if p < 0.05 and 0.60 <= score:
        reason_str = (
            f"tier2_person_of_interest (score={score:.4f} in [0.60, 0.80), "
            f"p={p:.4f} < 0.05, stability={stab:.1%})"
        )
        if reason_flags:
            reason_str += f" [{'; '.join(reason_flags)}]"
        return {
            "verdict": "PERSON_OF_INTEREST",
            "reason": reason_str,
            "evidence_strength": "MODERATE",
        }

    # Tier 3: INSUFFICIENT_EVIDENCE
    reason_str = (
        f"tier3_insufficient_evidence (score={score:.4f} < 0.60, "
        f"p={p:.4f}, stability={stab:.1%})"
    )
    if reason_flags:
        reason_str += f" [{'; '.join(reason_flags)}]"
    return {
        "verdict": "INSUFFICIENT_EVIDENCE",
        "reason": reason_str,
        "evidence_strength": "WEAK",
    }
