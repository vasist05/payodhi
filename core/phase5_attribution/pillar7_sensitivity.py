"""Pillar 7: Weather Sensitivity & Perturbation Stress-Testing.

Evaluates verdict stability under perturbed weather conditions (wind speed ±15%,
ocean current angle ±10°).

Adheres strictly to phase5Final.md rules:
- Callback run_drift_fn(wind_factor, current_angle_offset) returns {vessel_id: score}.
- Uses np.random.default_rng(seed=42) for reproducible perturbation sampling.
- Measures stability index: % of completed runs where the baseline top suspect remains #1.
- Catches and logs simulation crashes, excluding them from consistency calculation.
- If crashes > 10% -> flags UNSTABLE_WEATHER.

Edge cases handled:
1. n_runs < 10 -> force n_runs=10, note in reason
2. All runs crash -> stability_index=0.0, reason="all_runs_failed"
3. Top suspect changes excessively / consistency low -> flag INCONCLUSIVE
4. Two suspects tie ~90%+ -> flag MULTIPLE_CANDIDATES
5. Only 1 vessel in scene -> skip, stability_index=1.0, reason="single_vessel_stable"
"""

from __future__ import annotations

from collections import Counter
import logging
from typing import Any, Callable, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_RUNS = 100
MIN_RUNS = 10
DEFAULT_WIND_PERTURBATION = 0.15
DEFAULT_CURRENT_ANGLE_PERTURBATION = 10.0
DEFAULT_SEED = 42
CRASH_THRESHOLD_PCT = 0.10


def sensitivity_test(
    run_drift_fn: Callable[[float, float], Dict[str, float]],
    n_runs: int = DEFAULT_RUNS,
    wind_perturbation_pct: float = DEFAULT_WIND_PERTURBATION,
    current_angle_perturbation_deg: float = DEFAULT_CURRENT_ANGLE_PERTURBATION,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Run weather perturbation sensitivity stress-test.

    Args:
        run_drift_fn: Callable accepting (wind_factor, current_angle_offset_deg)
            and returning dict mapping vessel_id -> attribution score.
        n_runs: Number of perturbed runs to execute (default 100).
        wind_perturbation_pct: Relative wind speed perturbation range (default ±15%).
        current_angle_perturbation_deg: Current angle offset range (default ±10°).
        seed: Random generator seed for reproducibility (default 42).

    Returns:
        dict:
            stability_index (float): Fraction of runs where baseline top vessel was #1 [0.0 - 1.0].
            top_vessel_consistency (int): Number of runs where baseline top vessel was #1.
            n_runs_completed (int): Number of perturbation runs completed without crash.
            reason (str): Explanatory verdict and edge case annotations.
    """
    reason_notes: List[str] = []

    # Edge case 1: n_runs < 10 -> force n_runs=10
    total_runs = n_runs
    if total_runs < MIN_RUNS:
        logger.warning("n_runs=%d is below minimum of 10. Forcing n_runs=10.", total_runs)
        total_runs = MIN_RUNS
        reason_notes.append("forced_n_runs_min_10")

    # Execute baseline run (unperturbed: wind_factor=1.0, current_offset=0.0)
    try:
        baseline_scores = run_drift_fn(1.0, 0.0)
    except Exception as e:
        logger.error("Baseline drift run failed: %s", e)
        return {
            "stability_index": 0.0,
            "top_vessel_consistency": 0,
            "n_runs_completed": 0,
            "reason": "all_runs_failed (baseline_run_crashed)",
        }

    if not baseline_scores:
        return {
            "stability_index": 0.0,
            "top_vessel_consistency": 0,
            "n_runs_completed": 0,
            "reason": "all_runs_failed (baseline_returned_empty)",
        }

    # Edge case 5: Only 1 vessel in scene -> skip, stability_index=1.0
    if len(baseline_scores) == 1:
        single_vessel = next(iter(baseline_scores.keys()))
        logger.info("Only 1 vessel in scene (%s); sensitivity test skipped.", single_vessel)
        return {
            "stability_index": 1.0,
            "top_vessel_consistency": total_runs,
            "n_runs_completed": total_runs,
            "reason": "single_vessel_stable",
        }

    baseline_top_vessel = max(baseline_scores, key=lambda k: baseline_scores[k])

    rng = np.random.default_rng(seed=seed)
    wind_factors = rng.uniform(
        1.0 - wind_perturbation_pct,
        1.0 + wind_perturbation_pct,
        size=total_runs,
    )
    current_offsets = rng.uniform(
        -current_angle_perturbation_deg,
        current_angle_perturbation_deg,
        size=total_runs,
    )

    top_vessel_counts: Counter[str] = Counter()
    n_runs_completed = 0
    crashes = 0

    for i in range(total_runs):
        wf = float(wind_factors[i])
        co = float(current_offsets[i])
        try:
            run_scores = run_drift_fn(wf, co)
            if not run_scores:
                raise ValueError("Empty scores returned from drift simulation.")
            run_top = max(run_scores, key=lambda k: run_scores[k])
            top_vessel_counts[run_top] += 1
            n_runs_completed += 1
        except Exception as e:
            crashes += 1
            logger.warning("Perturbation run %d crashed: %s", i + 1, e)

    # Edge case 2: All runs crash
    if n_runs_completed == 0:
        return {
            "stability_index": 0.0,
            "top_vessel_consistency": 0,
            "n_runs_completed": 0,
            "reason": "all_runs_failed",
        }

    consistency = top_vessel_counts.get(baseline_top_vessel, 0)
    stability_index = round(consistency / n_runs_completed, 4)

    # Check crash percentage
    crash_pct = crashes / total_runs
    if crash_pct > CRASH_THRESHOLD_PCT:
        logger.warning("Drift simulation crashes (%.1f%%) exceeded 10%%.", crash_pct * 100)
        reason_notes.append("UNSTABLE_WEATHER")

    # Edge case 4: Two vessels tie ~90%+
    # If the top two vessels together represent >= 90% of runs, but top alone is < 85%
    most_common = top_vessel_counts.most_common(2)
    if len(most_common) >= 2:
        v1, count1 = most_common[0]
        v2, count2 = most_common[1]
        top_two_share = (count1 + count2) / n_runs_completed
        if top_two_share >= 0.90 and (count1 / n_runs_completed) < 0.85:
            reason_notes.append("MULTIPLE_CANDIDATES")

    # Edge case 3: Low stability / top suspect changes constantly
    if stability_index < 0.50:
        reason_notes.append("INCONCLUSIVE")
    elif stability_index >= 0.90:
        reason_notes.append("HIGH_STABILITY")

    final_reason = f"stability={stability_index:.1%} ({consistency}/{n_runs_completed} runs matched baseline top vessel)"
    if reason_notes:
        final_reason += f" [{'; '.join(reason_notes)}]"

    return {
        "stability_index": stability_index,
        "top_vessel_consistency": consistency,
        "n_runs_completed": n_runs_completed,
        "reason": final_reason,
    }
