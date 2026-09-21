"""Multi-Factor Evidential Fusion.

Fuses scores across all 7 attribution pillars into a composite score (0-100)
and calibrated probability (0-1).

Adheres strictly to phase5Final.md rules:
- Capacity Veto: if pillar4 multiplier == 0.0 -> total_score = 0.0 immediately.
- Default weights (sum to 1.0):
    cpa: 0.20, dark: 0.15, loiter: 0.15, capacity: 0.10, draft: 0.10,
    permutation: 0.15, sensitivity: 0.15
- Weighted sum -> total_score (clamped 0-100).
- Calibrated posterior score via Platt scaling (0-1).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

from core.phase5_attribution.calibration import calibrate_score

logger = logging.getLogger(__name__)

AHP_CONFIG_PATH = Path("config/ahp_weights.yaml")

DEFAULT_WEIGHTS: Dict[str, float] = {
    "cpa": 0.20,
    "dark": 0.15,
    "loiter": 0.15,
    "capacity": 0.10,
    "draft": 0.10,
    "permutation": 0.15,
    "sensitivity": 0.15,
}


def _load_ahp_weights() -> Dict[str, float]:
    """Load AHP weights from config file or fallback to DEFAULT_WEIGHTS."""
    if yaml is not None and AHP_CONFIG_PATH.exists():
        try:
            with open(AHP_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    weights = data.get("ahp_weights", data)
                    if isinstance(weights, dict):
                        return {str(k): float(v) for k, v in weights.items()}
        except Exception as e:
            logger.warning("Failed to load %s: %s. Using default weights.", AHP_CONFIG_PATH, e)
    return dict(DEFAULT_WEIGHTS)


def _extract_pillar_score(pillar_key: str, p_data: Dict[str, Any]) -> float:
    if not isinstance(p_data, dict):
        return 0.0

    if pillar_key in ("cpa", "pillar1_cpa"):
        return float(p_data.get("cpa_score", p_data.get("score", 0.0)))
    elif pillar_key in ("dark", "pillar2_dark"):
        return float(p_data.get("dark_vessel_score", p_data.get("score", 0.0)))
    elif pillar_key in ("loiter", "pillar3_loiter"):
        return float(p_data.get("loitering_score", p_data.get("score", 0.0)))
    elif pillar_key in ("capacity", "pillar4_capacity"):
        return float(p_data.get("multiplier", 1.0))
    elif pillar_key in ("draft", "pillar5_draft"):
        return float(p_data.get("draft_change_score", p_data.get("score", 0.0)))
    elif pillar_key in ("permutation", "pillar6_permutation"):
        if "p_value" in p_data:
            return max(0.0, 1.0 - float(p_data["p_value"]))
        return float(p_data.get("score", 0.0))
    elif pillar_key in ("sensitivity", "pillar7_sensitivity"):
        return float(p_data.get("stability_index", p_data.get("score", 0.0)))
    return float(p_data.get("score", 0.0))


def fuse_scores(
    pillar_results: Dict[str, Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Fuse 7-pillar results into total score (0-100) and calibrated score (0-1).

    Args:
        pillar_results: Dict containing results for pillars:
            'pillar1_cpa', 'pillar2_dark', 'pillar3_loiter', 'pillar4_capacity',
            'pillar5_draft', 'pillar6_permutation', 'pillar7_sensitivity'.
        weights: Optional custom weights mapping. Defaults to standard AHP weights.

    Returns:
        dict:
            total_score (float): 0.0 - 100.0.
            calibrated_score (float): 0.0 - 1.0.
            pillar_contributions (dict): Contribution breakdown by pillar.
            reason (str): Explanatory notes (e.g. capacity veto, fusion breakdown).
    """
    if not pillar_results:
        return {
            "total_score": 0.0,
            "calibrated_score": 0.0,
            "pillar_contributions": {},
            "reason": "no_pillar_results",
        }

    # Check Pillar 4 Capacity Veto immediately
    p4 = pillar_results.get("pillar4_capacity", pillar_results.get("capacity", {}))
    p4_multiplier = float(p4.get("multiplier", 1.0)) if isinstance(p4, dict) else 1.0

    if p4_multiplier == 0.0:
        logger.info("Pillar 4 capacity multiplier is 0.0; triggering immediate veto.")
        return {
            "total_score": 0.0,
            "calibrated_score": 0.0,
            "pillar_contributions": {"capacity_veto": 0.0},
            "reason": "capacity_veto (vessel capacity physically insufficient)",
        }

    # Resolve weights
    if weights is not None:
        w_map = {}
        for k, v in weights.items():
            short_k = k.replace("pillar", "").replace("_", "").lower()
            matched = False
            for def_k in DEFAULT_WEIGHTS:
                if def_k == short_k or def_k in short_k or short_k in def_k:
                    w_map[def_k] = float(v)
                    matched = True
                    break
            if not matched:
                w_map[k] = float(v)
    else:
        w_map = _load_ahp_weights()

    # Normalize weights sum
    total_w = sum(w_map.values())
    if total_w > 0:
        norm_weights = {k: v / total_w for k, v in w_map.items()}
    else:
        norm_weights = DEFAULT_WEIGHTS

    pillar_scores = {
        "cpa": _extract_pillar_score("cpa", pillar_results.get("pillar1_cpa", {})),
        "dark": _extract_pillar_score("dark", pillar_results.get("pillar2_dark", {})),
        "loiter": _extract_pillar_score("loiter", pillar_results.get("pillar3_loiter", {})),
        "capacity": _extract_pillar_score("capacity", p4),
        "draft": _extract_pillar_score("draft", pillar_results.get("pillar5_draft", {})),
        "permutation": _extract_pillar_score("permutation", pillar_results.get("pillar6_permutation", {})),
        "sensitivity": _extract_pillar_score("sensitivity", pillar_results.get("pillar7_sensitivity", {})),
    }

    # Check if all pillars are 0.0
    if all(s == 0.0 for s in pillar_scores.values()):
        return {
            "total_score": 0.0,
            "calibrated_score": 0.0,
            "pillar_contributions": {k: 0.0 for k in norm_weights},
            "reason": "all_pillars_zero",
        }

    contributions: Dict[str, float] = {}
    weighted_sum = 0.0
    for key, weight in norm_weights.items():
        score = pillar_scores.get(key, 0.0)
        contrib = weight * score
        contributions[key] = round(contrib * 100.0, 2)
        weighted_sum += contrib

    # Total score in [0.0, 100.0]
    total_score = max(0.0, min(100.0, round(weighted_sum * 100.0, 2)))

    # Calibrate score: scale [0, 100] to Platt domain [0, 5] so 50 -> 2.5 (prob 0.5)
    calibrated_val = calibrate_score((total_score / 100.0) * 5.0)
    calibrated_score = max(0.0, min(1.0, round(calibrated_val, 4)))

    reason = f"fused_attribution (total={total_score:.1f}/100, calibrated={calibrated_score:.4f})"

    return {
        "total_score": total_score,
        "calibrated_score": calibrated_score,
        "pillar_contributions": contributions,
        "reason": reason,
    }
