"""
core/phase1_sar/inference.py

Unified inference engine for Phase 1 SAR Oil Spill Detection.
Integrates preprocessing, sliding-window tiling, deep-learning U-Net segmentation,
post-processing, vectorization, and candidate generation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from PIL import Image

from core.phase1_sar.model import load_detection_model, SARUNetDetector
from core.phase1_sar.postprocess import (
    clean_binary_mask,
    create_spill_candidates,
    vectorize_mask,
)
from core.phase1_sar.preprocessing import load_and_normalize_sar
from core.phase1_sar.tiler import SceneTiler
from models.common.schema import SpillCandidate

log = logging.getLogger(__name__)


class SARSpillDetector:
    """
    High-level detector interface for Phase 1.
    Accepts full SAR satellite imagery (PNG, TIFF, array), runs sliding-window
    U-Net inference, extracts georeferenced oil spill polygons, and generates
    Phase 2 SpillCandidate patches.
    """

    def __init__(
        self,
        checkpoint_path: Optional[Union[str, Path]] = None,
        device: Optional[Union[str, torch.device]] = None,
        tile_size: int = 256,
        stride: int = 192,
        batch_size: int = 8,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        elif isinstance(device, str):
            self.device = torch.device(device)
        else:
            self.device = device

        self.model = load_detection_model(checkpoint_path=checkpoint_path, device=self.device)
        self.tiler = SceneTiler(tile_size=tile_size, stride=stride, batch_size=batch_size)
        log.info("SARSpillDetector initialized on %s (tile_size=%d, stride=%d)", self.device, tile_size, stride)

    def detect(
        self,
        image_input: Union[str, Path, np.ndarray, Image.Image],
        threshold: float = 0.50,
        min_pixels: int = 50,
        affine_transform: Optional[Tuple[float, ...]] = None,
        bbox_wgs84: Optional[Tuple[float, float, float, float]] = None,
        scene_id: Optional[str] = None,
        output_crops_dir: Optional[str] = "data/phase1_crops",
    ) -> Dict[str, Any]:
        """
        Execute full detection on a SAR scene.

        Args:
            image_input: Path to image or loaded numpy/PIL image.
            threshold: Probability threshold for oil detection (default 0.50).
            min_pixels: Minimum connected oil pixels to keep (removes speckles).
            affine_transform: Optional 6-element affine transform for GeoTIFF.
            bbox_wgs84: Optional (min_lon, min_lat, max_lon, max_lat).
            scene_id: Optional UUID/identifier of the parent satellite scene.
            output_crops_dir: Directory to save 256x256 candidate patches for Phase 2.

        Returns:
            Dict containing:
              - 'detections': List of detected spill dicts (geometry, centroid, area_sq_km, confidence)
              - 'candidates': List of SpillCandidate objects for Phase 2 verification
              - 'probability_map': Full 2D float32 probability array [H, W]
              - 'binary_mask': Cleaned 2D uint8 mask [H, W]
              - 'spill_count': Number of discrete spills detected
        """
        # 1. Preprocess & Normalize
        norm_img = load_and_normalize_sar(image_input)
        h, w = norm_img.shape
        log.info("Processing SAR scene (%d x %d)", h, w)

        # 2. Run Sliding-Window Tiling & U-Net Inference
        prob_map = self.tiler.predict_scene(
            image_2d=norm_img,
            model=self.model,
            device=self.device,
        )

        # 3. Post-Process & Clean Binary Mask
        clean_mask = clean_binary_mask(
            prob_mask=prob_map,
            threshold=threshold,
            min_pixels=min_pixels,
        )

        # 4. Vectorize & Compute Areas and Coordinates
        detections = vectorize_mask(
            binary_mask=clean_mask,
            prob_mask=prob_map,
            affine_transform=affine_transform,
            bbox_wgs84=bbox_wgs84,
            min_pixels=min_pixels,
        )

        # 5. Extract SpillCandidate crops for Phase 2 Filter
        candidates = create_spill_candidates(
            detections=detections,
            raw_image_2d=norm_img,
            scene_id=scene_id,
            output_dir=output_crops_dir,
            padding=32,
        )

        log.info("Detected %d oil spill candidates in scene", len(detections))

        return {
            "detections": detections,
            "candidates": candidates,
            "probability_map": prob_map,
            "binary_mask": clean_mask,
            "spill_count": len(detections),
            "image_shape": (h, w),
        }
