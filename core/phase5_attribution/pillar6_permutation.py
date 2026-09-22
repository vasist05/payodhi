"""Pillar 6: The 5,000-Run Null Permutation Test (Statistical Proof).

Evaluates whether the top candidate's attribution score is statistically
distinguishable from random background maritime traffic (p < 0.05).

Adheres strictly to phase5Final.md rules:
- Uses np.random.default_rng(seed=42) for reproducible, vectorized execution.
- Builds random null baseline distribution by resampling non-top background scores.
- Computes baseline 99th percentile and empirical p-value:
      p_value = (count of permutations where max >= top_score) / n_permutations
- If p_value > 0.05 -> flags INSUFFICIENT_EVIDENCE candidate.

Edge cases handled:
1. Only 1 vessel -> p_value = 0.5, reason = "single_suspect"
2. All scores identical -> p_value = 1.0, reason = "all_scores_identical"
3. Top score < 0.3 -> skip permutation, p_value = 1.0, reason = "all_scores_low"
4. Empty dict -> return p_value = 1.0, reason = "no_vessels"
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_PERMUTATIONS = 5000
DEFAULT_SEED = 42
MIN_TOP_SCORE_THRESHOLD = 0.30
SIGNIFICANCE_THRESHOLD = 0.05


def permutation_test(
    vessel_scores: Dict[str, float],
    n_permutations: int = DEFAULT_PERMUTATIONS,
    seed: int = DEFAULT_SEED,
) -> Dict[str, any]:
    """Run Monte Carlo null permutation test on candidate vessel scores.

    Args:
        vessel_scores: Dict mapping vessel_id -> composite attribution score.
        n_permutations: Number of permutation/bootstrap shuffles (default 5000).
        seed: Random generator seed for reproducibility (default 42).

    Returns:
        dict:
            p_value (float): Empirical p-value.
            baseline_99th (float): 99th percentile of background distribution.
            top_vessel_id (str): Identifier of the top candidate vessel.
            top_score (float): Score of the top candidate vessel.
            reason (str): Explanatory verdict and edge case tags.
    """
    # Edge case 4: Empty dict
    if not vessel_scores:
        logger.warning("Empty vessel scores dictionary provided to permutation test.")
        return {
            "p_value": 1.0,
            "baseline_99th": 0.0,
            "top_vessel_id": "",
            "top_score": 0.0,
            "reason": "no_vessels",
        }

    # Find top candidate
    top_vessel_id = max(vessel_scores, key=lambda k: vessel_scores[k])
    top_score = float(vessel_scores[top_vessel_id])

    # Edge case 1: Only 1 vessel
    if len(vessel_scores) == 1:
        logger.info("Single vessel in scene; permutation skipped.")
        return {
            "p_value": 0.5,
            "baseline_99th": round(top_score, 4),
            "top_vessel_id": top_vessel_id,
            "top_score": round(top_score, 4),
            "reason": "single_suspect",
        }

    scores_list = list(vessel_scores.values())

    # Edge case 2: All scores identical
    if all(s == scores_list[0] for s in scores_list):
        logger.info("All vessel scores are identical (%.4f); no statistical contrast.", scores_list[0])
        return {
            "p_value": 1.0,
            "baseline_99th": round(scores_list[0], 4),
            "top_vessel_id": top_vessel_id,
            "top_score": round(top_score, 4),
            "reason": "all_scores_identical",
        }

    # Edge case 3: Top score < 0.3
    if top_score < MIN_TOP_SCORE_THRESHOLD:
        logger.info("Top vessel score %.4f is below 0.3; skipping permutation.", top_score)
        return {
            "p_value": 1.0,
            "baseline_99th": round(top_score, 4),
            "top_vessel_id": top_vessel_id,
            "top_score": round(top_score, 4),
            "reason": "all_scores_low",
        }

    # Background traffic distribution: all candidate scores excluding the top suspect
    bg_scores = np.array([s for vid, s in vessel_scores.items() if vid != top_vessel_id], dtype=np.float64)

    rng = np.random.default_rng(seed=seed)

    # Vectorized Monte Carlo permutation / bootstrap of the null background traffic
    # For each shuffle, randomly resample background traffic and record the maximum
    resamples = rng.choice(bg_scores, size=(n_permutations, len(bg_scores)), replace=True)
    shuffled_maxes = np.max(resamples, axis=1)

    baseline_99th = float(np.percentile(shuffled_maxes, 99))
    count_ge = int(np.sum(shuffled_maxes >= top_score))
    p_value = float(count_ge / n_permutations)

    if p_value > SIGNIFICANCE_THRESHOLD:
        reason = f"INSUFFICIENT_EVIDENCE candidate (p={p_value:.4f} > 0.05, baseline_99th={baseline_99th:.4f})"
    else:
        reason = f"statistically_significant (p={p_value:.4f} < 0.05, baseline_99th={baseline_99th:.4f})"

    return {
        "p_value": round(p_value, 4),
        "baseline_99th": round(baseline_99th, 4),
        "top_vessel_id": top_vessel_id,
        "top_score": round(top_score, 4),
        "reason": reason,
    }
