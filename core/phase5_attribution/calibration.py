"""Calibration: Probability Calibration via Platt Scaling.

Converts raw multi-factor attribution scores into calibrated posterior probabilities.
Formula: calibrated = 1 / (1 + exp(-a * raw + b))
Default params: a = 2.0, b = 5.0 (loaded from config/calibration.yaml if present).
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_A = 2.0
DEFAULT_B = 5.0
CONFIG_PATH = Path("config/calibration.yaml")


def _load_params_from_yaml() -> Tuple[float, float]:
    if yaml is not None and CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    platt = data.get("platt_scaling", data)
                    a = float(platt.get("a", DEFAULT_A))
                    b = float(platt.get("b", DEFAULT_B))
                    return a, b
        except Exception:
            pass
    return DEFAULT_A, DEFAULT_B


def calibrate_score(raw_score: float, calibration_data: Optional[Dict[str, Any]] = None) -> float:
    """Apply Platt scaling to convert a raw attribution score into a calibrated probability.

    calibrated = 1 / (1 + exp(-a * raw + b))

    Args:
        raw_score: Raw score value.
        calibration_data: Optional dictionary containing {'a': float, 'b': float}.

    Returns:
        float: Calibrated probability in [0.0, 1.0].
    """
    if raw_score is None or math.isnan(raw_score):
        return 0.0

    if calibration_data is not None:
        a = float(calibration_data.get("a", DEFAULT_A))
        b = float(calibration_data.get("b", DEFAULT_B))
    else:
        a, b = _load_params_from_yaml()

    # Calculate exponent: -a * raw + b
    z = -a * float(raw_score) + b

    # Prevent overflow in exp
    if z > 100.0:
        return 0.0
    elif z < -100.0:
        return 1.0

    calibrated = 1.0 / (1.0 + math.exp(z))
    # Strict clamping to [0.0, 1.0]
    return max(0.0, min(1.0, round(calibrated, 4)))
