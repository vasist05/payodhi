"""
core/phase1_sar/preprocessing.py

Exact preprocessing pipeline for SAR satellite imagery matching the training configuration
of the base U-Net model (IoU 0.7441).

Preprocessing steps:
1. Grayscale conversion: Image.open(...).convert("L") (values 0-255).
2. Normalization: img.float() / 255.0 -> [0.0, 1.0].
3. Bounding box detection with 32px padding around oil pixels (mask > 127).
4. Signal verification: minimum oil fraction check (MIN_SPILL_FRAC = 0.05).
5. Resize / Crop to standard 256x256 tiles.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple, Union

import numpy as np
from PIL import Image
import torch

log = logging.getLogger(__name__)

TARGET_SIZE = (256, 256)
PADDING_PX = 32
MIN_SPILL_FRAC = 0.05
OIL_PIXEL_THRESHOLD = 127


def load_and_normalize_sar(
    image_input: Union[str, np.ndarray, Image.Image],
) -> np.ndarray:
    """
    Load an image or array and normalize to [0.0, 1.0] single-channel float32.

    Returns:
        np.ndarray of shape (H, W) with float32 values in [0.0, 1.0].
    """
    if isinstance(image_input, (str, bytes)):
        pil_img = Image.open(image_input).convert("L")
        arr = np.array(pil_img, dtype=np.float32)
    elif isinstance(image_input, Image.Image):
        pil_img = image_input.convert("L")
        arr = np.array(pil_img, dtype=np.float32)
    elif isinstance(image_input, np.ndarray):
        if image_input.ndim == 3:
            # If 3-channel RGB or multi-band, take first channel or convert to grayscale
            if image_input.shape[2] == 1:
                arr = image_input[:, :, 0].astype(np.float32)
            else:
                arr = (
                    0.2989 * image_input[:, :, 0]
                    + 0.5870 * image_input[:, :, 1]
                    + 0.1140 * image_input[:, :, 2]
                ).astype(np.float32)
        elif image_input.ndim == 2:
            arr = image_input.astype(np.float32)
        else:
            raise ValueError(f"Unsupported array shape: {image_input.shape}")
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    # Check if image is in [0, 255] or already [0, 1]
    max_val = float(arr.max()) if arr.size > 0 else 1.0
    if max_val > 1.0:
        arr = arr / 255.0

    return np.clip(arr, 0.0, 1.0).astype(np.float32)


def to_torch_tensor(
    arr_2d: np.ndarray,
    device: Optional[Union[str, torch.device]] = None,
) -> torch.Tensor:
    """
    Convert (H, W) float32 numpy array into torch.Tensor of shape (1, 1, H, W).
    """
    t = torch.from_numpy(arr_2d).unsqueeze(0).unsqueeze(0).float()
    if device is not None:
        t = t.to(device)
    return t


def find_spill_bounding_box(
    mask: np.ndarray,
    padding: int = PADDING_PX,
    threshold: float = 0.5,
) -> Optional[Tuple[int, int, int, int]]:
    """
    Find bounding box (y0, y1, x0, x1) containing oil pixels with padding.

    mask: 2D array of predictions (probabilities in [0, 1] or binary 0/255).
    threshold: binary threshold (0.5 for proba, or 127 for uint8).
    """
    if mask.dtype == np.uint8 and mask.max() > 1:
        oil_mask = mask > OIL_PIXEL_THRESHOLD
    else:
        oil_mask = mask > threshold

    if oil_mask.sum() == 0:
        return None

    rows = np.any(oil_mask, axis=1)
    cols = np.any(oil_mask, axis=0)

    y_indices = np.where(rows)[0]
    x_indices = np.where(cols)[0]

    if len(y_indices) == 0 or len(x_indices) == 0:
        return None

    y0, y1 = y_indices[0], y_indices[-1]
    x0, x1 = x_indices[0], x_indices[-1]

    # Add padding
    h, w = mask.shape[:2]
    y0_pad = max(0, int(y0 - padding))
    y1_pad = min(h, int(y1 + padding + 1))
    x0_pad = max(0, int(x0 - padding))
    x1_pad = min(w, int(x1 + padding + 1))

    return (y0_pad, y1_pad, x0_pad, x1_pad)


def check_spill_fraction(
    crop_mask: np.ndarray,
    min_fraction: float = MIN_SPILL_FRAC,
    threshold: float = 0.5,
) -> Tuple[bool, float]:
    """
    Verify crop has >= min_fraction oil pixels.
    Returns (is_valid, oil_fraction).
    """
    if crop_mask.size == 0:
        return False, 0.0

    if crop_mask.dtype == np.uint8 and crop_mask.max() > 1:
        oil_pixels = np.sum(crop_mask > OIL_PIXEL_THRESHOLD)
    else:
        oil_pixels = np.sum(crop_mask > threshold)

    frac = float(oil_pixels) / float(crop_mask.size)
    return (frac >= min_fraction, frac)


def crop_and_resize(
    image: np.ndarray,
    bbox: Tuple[int, int, int, int],
    target_size: Tuple[int, int] = TARGET_SIZE,
) -> np.ndarray:
    """
    Crop region (y0, y1, x0, x1) and resize to target_size (default 256x256).
    """
    y0, y1, x0, x1 = bbox
    cropped = image[y0:y1, x0:x1]

    # Resize using PIL for consistent interpolation
    if cropped.dtype != np.uint8:
        # Convert float [0, 1] to uint8 for PIL resize then back
        pil_crop = Image.fromarray((cropped * 255.0).astype(np.uint8))
        resized = pil_crop.resize(target_size, Image.Resampling.BILINEAR)
        return (np.array(resized, dtype=np.float32) / 255.0).astype(np.float32)
    else:
        pil_crop = Image.fromarray(cropped)
        resized = pil_crop.resize(target_size, Image.Resampling.NEAREST)
        return np.array(resized)
