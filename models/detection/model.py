"""
models/detection/model.py

Alias to core.phase1_sar.model for modular access per sih-143-plan.md.
"""
from core.phase1_sar.model import SARUNetDetector, build_model, load_detection_model

__all__ = ["SARUNetDetector", "build_model", "load_detection_model"]
