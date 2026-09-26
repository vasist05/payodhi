"""
core/phase1_sar/tiler.py

Sliding-window tiling and full-scene reconstruction engine for Phase 1 SAR detection.
Slices large Sentinel-1 SAR scenes (e.g. 2048x2048 or larger GeoTIFF swaths) into 256x256 tiles,
runs batch inference, and reconstructs the seamless global probability map with overlap blending.
"""

from __future__ import annotations

import logging
from typing import Generator, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

log = logging.getLogger(__name__)


def generate_tiles(
    h: int,
    w: int,
    tile_size: int = 256,
    stride: int = 192,
) -> List[Tuple[int, int, int, int]]:
    """
    Generate tile bounding boxes (y0, y1, x0, x1) covering (h, w).
    Guarantees every tile is exactly (tile_size, tile_size) without zero-padding distortion.
    """
    if h <= tile_size and w <= tile_size:
        return [(0, h, 0, w)]

    y_starts = list(range(0, max(1, h - tile_size + 1), stride))
    if not y_starts or (y_starts[-1] + tile_size < h):
        y_starts.append(max(0, h - tile_size))
    # Deduplicate while preserving order
    y_starts = list(dict.fromkeys(y_starts))

    x_starts = list(range(0, max(1, w - tile_size + 1), stride))
    if not x_starts or (x_starts[-1] + tile_size < w):
        x_starts.append(max(0, w - tile_size))
    x_starts = list(dict.fromkeys(x_starts))

    tiles = []
    for y0 in y_starts:
        y1 = min(h, y0 + tile_size)
        for x0 in x_starts:
            x1 = min(w, x0 + tile_size)
            tiles.append((y0, y1, x0, x1))

    return tiles

    return tiles


def get_blend_weight_mask(tile_size: int = 256) -> np.ndarray:
    """
    Create a 2D 2-linear/cosine blending mask so overlaps smoothly blend
    and border discontinuities are avoided.
    """
    x = np.linspace(-1, 1, tile_size)
    y = np.linspace(-1, 1, tile_size)
    xx, yy = np.meshgrid(x, y)
    r = np.sqrt(xx**2 + yy**2)
    # Cosine taper from center to border
    w = 0.5 * (1 + np.cos(np.clip(r, 0, 1) * np.pi))
    w = np.maximum(w, 0.05)  # Avoid exact zeros at corners
    return w.astype(np.float32)


class SceneTiler:
    """
    Manages sliding-window tiling and stitched prediction for large SAR scenes.
    """

    def __init__(
        self,
        tile_size: int = 256,
        stride: int = 192,
        batch_size: int = 8,
    ):
        self.tile_size = tile_size
        self.stride = stride
        self.batch_size = batch_size
        self.weight_mask = get_blend_weight_mask(tile_size)

    @torch.no_grad()
    def predict_scene(
        self,
        image_2d: np.ndarray,
        model: nn.Module,
        device: torch.device,
    ) -> np.ndarray:
        """
        Run prediction over an arbitrary size 2D SAR image [H, W] normalized to [0.0, 1.0].
        - For scenes up to 1024x1024: uses direct Fully-Convolutional inference with 32px padding for maximum global context.
        - For massive swaths (> 1024x1024): uses sliding-window tiling with overlap blending.

        Returns:
            np.ndarray of shape (H, W) with continuous oil probabilities in [0.0, 1.0].
        """
        h, w = image_2d.shape
        model.eval()

        # For images up to 1024x1024, direct FCN inference preserves full spatial context
        if max(h, w) <= 1024:
            pad_h = (32 - (h % 32)) % 32
            pad_w = (32 - (w % 32)) % 32
            if pad_h > 0 or pad_w > 0:
                padded = np.pad(image_2d, ((0, pad_h), (0, pad_w)), mode="reflect")
            else:
                padded = image_2d

            t = torch.from_numpy(padded).unsqueeze(0).unsqueeze(0).to(device)
            logits = model(t)
            prob = torch.sigmoid(logits).squeeze().cpu().numpy()
            return np.clip(prob[:h, :w], 0.0, 1.0).astype(np.float32)

        # For massive scenes (> 1024x1024), use sliding window
        stride = min(self.stride, 256)
        tile_size = self.tile_size
        tiles = generate_tiles(h, w, tile_size, stride)

        prob_map = np.zeros((h, w), dtype=np.float32)
        weight_map = np.zeros((h, w), dtype=np.float32)

        # Process in batches
        for i in range(0, len(tiles), self.batch_size):
            batch_coords = tiles[i : i + self.batch_size]
            batch_patches = []

            for y0, y1, x0, x1 in batch_coords:
                patch = image_2d[y0:y1, x0:x1]
                # In case border tile is not exactly tile_size
                if patch.shape != (self.tile_size, self.tile_size):
                    temp = np.zeros((self.tile_size, self.tile_size), dtype=np.float32)
                    temp[: patch.shape[0], : patch.shape[1]] = patch
                    patch = temp
                batch_patches.append(patch)

            batch_tensor = (
                torch.from_numpy(np.stack(batch_patches, axis=0))
                .unsqueeze(1)
                .to(device)
            )

            logits = model(batch_tensor)
            probs = torch.sigmoid(logits).squeeze(1).cpu().numpy()  # [B, H, W]

            for idx, (y0, y1, x0, x1) in enumerate(batch_coords):
                p = probs[idx]
                target_h = y1 - y0
                target_w = x1 - x0
                w_mask = self.weight_mask[:target_h, :target_w]

                prob_map[y0:y1, x0:x1] += p[:target_h, :target_w] * w_mask
                weight_map[y0:y1, x0:x1] += w_mask

        # Normalize overlapping blends
        weight_map = np.maximum(weight_map, 1e-6)
        prob_map = prob_map / weight_map

        # Crop back to original dimensions
        output_prob = prob_map[:h, :w]
        return np.clip(output_prob, 0.0, 1.0).astype(np.float32)
