"""
Phase 3 Hydrodynamic Drift Model (OpenDrift / OpenOil)
Handles backward trajectory origin prediction and forward vessel release verification.
"""

from core.phase3_drift.drift_model.runner import run_backward, run_forward
from core.phase3_drift.drift_model.sampler import sample_scenarios
from core.phase3_drift.drift_model.aggregate import contour_to_polygon, build_heatmap, confidence_contours, peak_location
from core.phase3_drift.drift_model.orchestrate import full_backward_pipeline, run_backward_ensemble
from core.phase3_drift.drift_model.forcing import make_synthetic_wind, make_synthetic_current, load_forcing

__all__ = [
    "run_backward",
    "run_forward",
    "sample_scenarios",
    "full_backward_pipeline",
    "run_backward_ensemble",
    "contour_to_polygon",
    "build_heatmap",
    "confidence_contours",
    "peak_location",
    "make_synthetic_wind",
    "make_synthetic_current",
    "load_forcing",
]
