"""
core/phase1_sar

Phase 1 — SAR Oil Spill Detection Foundation module.
"""

from core.phase1_sar.inference import SARSpillDetector
from core.phase1_sar.model import SARUNetDetector, build_model, load_detection_model
from core.phase1_sar.postprocess import clean_binary_mask, pixel_to_geo, vectorize_mask
from core.phase1_sar.preprocessing import (
    load_and_normalize_sar,
    find_spill_bounding_box,
    crop_and_resize,
)
from core.phase1_sar.tiler import SceneTiler

__all__ = [
    "SARSpillDetector",
    "SARUNetDetector",
    "build_model",
    "load_detection_model",
    "load_and_normalize_sar",
    "find_spill_bounding_box",
    "crop_and_resize",
    "SceneTiler",
    "clean_binary_mask",
    "vectorize_mask",
    "pixel_to_geo",
]
