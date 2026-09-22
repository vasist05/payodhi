"""Legal & Court Admissibility Layer: 3-Tiered Verdict Classification.

Categorizes forensic evidence into legally defensible tiers under UNCLOS / MARPOL:
- Tier 1 PROSECUTABLE: p_value < 0.01 AND calibrated_score >= 0.80 AND stability_index >= 0.90
- Tier 2 PERSON_OF_INTEREST: p_value < 0.05 AND 0.60 <= calibrated_score < 0.80
- Tier 3 INSUFFICIENT_EVIDENCE: All other conditions (or if p_value > 0.05, enforcing Null Hypothesis H0)

DB NOTE: verdict values MUST match VerdictEnum in backend/app/db/models/enums.py:
  'prosecutable', 'person_of_interest', 'insufficient_evidence'  (lowercase, underscored).

Edge cases handled:
1. calibrated_score > 1.0 -> clamp to 1.0, note in reason
2. calibrated_score < 0.0 -> clamp to 0.0, note in reason
3. NaN or None -> return insufficient_evidence with "invalid_score"
4. All pillars 0.0 -> insufficient_evidence with "all_pillars_zero"
5. Capacity veto -> insufficient_evidence with "capacity_veto"
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

VERDICT_CONFIG_PATH = Path("config/verdict_thresholds.yaml")

DEFAULT_TIER1_MAX_P = 0.01
DEFAULT_TIER1_MIN_SCORE = 0.80
DEFAULT_TIER1_MIN_STAB = 0.90
DEFAULT_TIER2_MAX_P = 0.05
DEFAULT_TIER2_MIN_SCORE = 0.60
DEFAULT_NULL_HYPOTHESIS_CUTOFF = 0.05


def _load_thresholds() -> Dict[str, Any]:
    """Load threshold configuration from YAML file or return defaults."""
    if yaml is not None and VERDICT_CONFIG_PATH.exists():
        try:
            with open(VERDICT_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    cfg = data.get("verdict_thresholds", data)
                    t1 = cfg.get("tier1_prosecutable", {})
                    t2 = cfg.get("tier2_person_of_interest", {})
                    return {
                        "tier1_max_p": float(t1.get("max_p_value", DEFAULT_TIER1_MAX_P)),
                        "tier1_min_score": float(t1.get("min_calibrated_score", DEFAULT_TIER1_MIN_SCORE)),
                        "tier1_min_stab": float(t1.get("min_stability_index", DEFAULT_TIER1_MIN_STAB)),
                        "tier2_max_p": float(t2.get("max_p_value", DEFAULT_TIER2_MAX_P)),
                        "tier2_min_score": float(t2.get("min_calibrated_score", DEFAULT_TIER2_MIN_SCORE)),
                        "null_cutoff": float(cfg.get("null_hypothesis_cutoff", DEFAULT_NULL_HYPOTHESIS_CUTOFF)),
                    }
        except Exception as e:
            logger.warning("Failed to load %s: %s. Using default thresholds.", VERDICT_CONFIG_PATH, e)
    return {
        "tier1_max_p": DEFAULT_TIER1_MAX_P,
        "tier1_min_score": DEFAULT_TIER1_MIN_SCORE,
        "tier1_min_stab": DEFAULT_TIER1_MIN_STAB,
        "tier2_max_p": DEFAULT_TIER2_MAX_P,
        "tier2_min_score": DEFAULT_TIER2_MIN_SCORE,
        "null_cutoff": DEFAULT_NULL_HYPOTHESIS_CUTOFF,
    }


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
            "db_verdict": "insufficient_evidence",
            "reason": "capacity_veto (vessel capacity physically insufficient)",
            "evidence_strength": "NONE",
        }

    # Edge case 4: All pillars 0.0
    if "all_pillars_zero" in ctx or (calibrated_score == 0.0 and p_value is None):
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "db_verdict": "insufficient_evidence",
            "reason": "all_pillars_zero (no incriminating anomalies detected)",
            "evidence_strength": "NONE",
        }

    # Edge case 3: NaN or None
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
            "db_verdict": "insufficient_evidence",
            "reason": "invalid_score (missing or NaN metrics)",
            "evidence_strength": "NONE",
        }

    # Edge case 1 & 2: Clamp calibrated_score to [0.0, 1.0]
    reason_flags = []
    score = calibrated_score
    if score > 1.0:
        score = 1.0
        reason_flags.append("score_clamped_to_1.0")
    elif score < 0.0:
        score = 0.0
        reason_flags.append("score_clamped_to_0.0")

    p = max(0.0, min(1.0, p_value))
    stab = max(0.0, min(1.0, stability_index))

    thresh = _load_thresholds()

    # Strict enforcement of Null Hypothesis H0
    # If p_value > null_cutoff (0.05), cannot reject H0 -> INSUFFICIENT_EVIDENCE
    if p > thresh["null_cutoff"]:
        reason_str = f"H0_null_hypothesis_accepted (p={p:.4f} > {thresh['null_cutoff']})"
        if reason_flags:
            reason_str += f" [{'; '.join(reason_flags)}]"
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "db_verdict": "insufficient_evidence",
            "reason": reason_str,
            "evidence_strength": "WEAK",
        }

    # Tier 1: PROSECUTABLE
    # Criteria: p < tier1_max_p AND calibrated_score >= tier1_min_score AND stability_index >= tier1_min_stab
    if p < thresh["tier1_max_p"] and score >= thresh["tier1_min_score"] and stab >= thresh["tier1_min_stab"]:
        reason_str = (
            f"tier1_prosecutable (score={score:.4f} >= {thresh['tier1_min_score']}, "
            f"p={p:.4f} < {thresh['tier1_max_p']}, stability={stab:.1%} >= {thresh['tier1_min_stab']:.0%})"
        )
        if reason_flags:
            reason_str += f" [{'; '.join(reason_flags)}]"
        return {
            "verdict": "PROSECUTABLE",
            "db_verdict": "prosecutable",
            "reason": reason_str,
            "evidence_strength": "STRONG",
        }

    # Tier 2: PERSON_OF_INTEREST
    # Criteria: p < tier2_max_p AND calibrated_score >= tier2_min_score
    if p < thresh["tier2_max_p"] and score >= thresh["tier2_min_score"]:
        reason_str = (
            f"tier2_person_of_interest (score={score:.4f} >= {thresh['tier2_min_score']}, "
            f"p={p:.4f} < {thresh['tier2_max_p']}, stability={stab:.1%})"
        )
        if reason_flags:
            reason_str += f" [{'; '.join(reason_flags)}]"
        return {
            "verdict": "PERSON_OF_INTEREST",
            "db_verdict": "person_of_interest",
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
        "db_verdict": "insufficient_evidence",
        "reason": reason_str,
        "evidence_strength": "WEAK",
    }
