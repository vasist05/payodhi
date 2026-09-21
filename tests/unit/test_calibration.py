"""Unit tests for Probability Calibration (Platt Scaling)."""

import math
import pytest
from core.phase5_attribution.calibration import calibrate_score


def test_default_platt_scaling():
    """Test default parameters a=2.0, b=5.0: score 2.5 produces 0.5 probability."""
    # z = -2.0 * 2.5 + 5.0 = 0.0 -> 1 / (1 + 1) = 0.5
    prob = calibrate_score(2.5)
    assert pytest.approx(prob, abs=1e-3) == 0.50


def test_high_score_produces_high_probability():
    """Test high raw score produces high confidence (> 0.90)."""
    # z = -2.0 * 4.0 + 5.0 = -3.0 -> 1 / (1 + e^-3) = 0.9526
    prob = calibrate_score(4.0)
    assert prob >= 0.95


def test_low_score_produces_low_probability():
    """Test low raw score produces low probability (< 0.10)."""
    # z = -2.0 * 1.0 + 5.0 = 3.0 -> 1 / (1 + e^3) = 0.0474
    prob = calibrate_score(1.0)
    assert prob <= 0.05


def test_custom_calibration_data():
    """Test passing custom calibration dictionary overrides defaults."""
    custom_data = {"a": 1.0, "b": 0.0}
    # z = -1.0 * 0.0 + 0.0 = 0 -> prob = 0.5
    prob = calibrate_score(0.0, calibration_data=custom_data)
    assert pytest.approx(prob, abs=1e-3) == 0.50


def test_edge_cases_nan_and_extremes():
    """Test NaN and extreme inputs are clamped to [0.0, 1.0]."""
    assert calibrate_score(float("nan")) == 0.0
    assert calibrate_score(100.0) == 1.0
    assert calibrate_score(-100.0) == 0.0
