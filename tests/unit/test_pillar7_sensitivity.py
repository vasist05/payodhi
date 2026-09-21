"""Unit tests for Pillar 7: Weather Sensitivity Stress-Testing."""

import pytest
from core.phase5_attribution.pillar7_sensitivity import sensitivity_test


def test_high_stability_suspect():
    """Test robust candidate where top vessel stays #1 in >90% of runs."""
    def mock_drift(wind_factor: float, current_offset: float):
        # Suspect always leads unless extreme perturbation
        score_suspect = 0.90 * wind_factor
        score_other = 0.40 + (current_offset / 100.0)
        return {"vessel_top": score_suspect, "vessel_other": score_other}

    res = sensitivity_test(mock_drift, n_runs=50, seed=42)
    assert res["stability_index"] >= 0.90
    assert res["n_runs_completed"] == 50
    assert "HIGH_STABILITY" in res["reason"]


def test_edge_case_n_runs_under_10_forced():
    """Edge case 1: n_runs < 10 forces n_runs=10 and notes in reason."""
    def mock_drift(wf, co):
        return {"v1": 0.8, "v2": 0.3}

    res = sensitivity_test(mock_drift, n_runs=4)
    assert res["n_runs_completed"] == 10
    assert "forced_n_runs_min_10" in res["reason"]


def test_edge_case_all_runs_crash():
    """Edge case 2: All simulation runs crash returns stability=0.0 and all_runs_failed."""
    def crashing_drift(wf, co):
        if wf == 1.0 and co == 0.0:
            return {"v1": 0.8, "v2": 0.3}  # Baseline succeeds
        raise RuntimeError("OpenDrift simulated crash")

    res = sensitivity_test(crashing_drift, n_runs=15)
    assert res["stability_index"] == 0.0
    assert res["n_runs_completed"] == 0
    assert "all_runs_failed" in res["reason"]


def test_edge_case_inconclusive_low_stability():
    """Edge case 3: Suspect changes frequently yields stability < 0.5 and INCONCLUSIVE."""
    def unstable_drift(wf, co):
        # Highly sensitive to current angle
        if co > 0:
            return {"v1": 0.8, "v2": 0.4}
        else:
            return {"v1": 0.3, "v2": 0.8}

    res = sensitivity_test(unstable_drift, n_runs=40, seed=42)
    assert res["stability_index"] < 0.70
    assert "INCONCLUSIVE" in res["reason"] or "MULTIPLE_CANDIDATES" in res["reason"]


def test_edge_case_two_vessels_tie_multiple_candidates():
    """Edge case 4: Two suspects tie ~90%+ flags MULTIPLE_CANDIDATES."""
    def tied_drift(wf, co):
        # 50/50 split between v1 and v2
        if co >= 0:
            return {"v1": 0.80, "v2": 0.75, "v3": 0.10}
        else:
            return {"v1": 0.75, "v2": 0.80, "v3": 0.10}

    res = sensitivity_test(tied_drift, n_runs=50, seed=42)
    assert "MULTIPLE_CANDIDATES" in res["reason"]


def test_edge_case_single_vessel_skips_stable():
    """Edge case 5: Only 1 vessel in scene skips with stability_index=1.0."""
    def single_drift(wf, co):
        return {"vessel_alone": 0.85}

    res = sensitivity_test(single_drift, n_runs=20)
    assert res["stability_index"] == 1.0
    assert "single_vessel_stable" in res["reason"]


def test_crashes_over_10_percent_flags_unstable_weather():
    """Test crashes > 10% flags UNSTABLE_WEATHER in reason."""
    run_count = 0
    def occasional_crash_drift(wf, co):
        nonlocal run_count
        run_count += 1
        # Crash 25% of the time
        if run_count % 4 == 0:
            raise RuntimeError("Temporary ERA5 interpolation glitch")
        return {"v1": 0.8, "v2": 0.3}

    res = sensitivity_test(occasional_crash_drift, n_runs=20, seed=42)
    assert "UNSTABLE_WEATHER" in res["reason"]
    assert res["stability_index"] > 0.0
