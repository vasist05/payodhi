"""
core/phase1_sar/dataset.py

Dataset loaders and training data preprocessing pipeline for Phase 1.
Implements the exact Zenodo + Kaggle preprocessing strategy:
- Finding oil pixel bounding box with 32px padding
- Filtering empty masks and low-signal crops (< 5% oil content)
- 0-255 -> 0.0-1.0 float normalization
- SAR-invariant spatial and radiometric augmentations
"""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

import numpy as np
from PIL import Image
import torch
from torch.utils.data import Dataset

try:
    import albumentations as A
    from albumentations.pytorch import ToTensorV2
    ALBUMENTATIONS_AVAILABLE = True
except ImportError:
    ALBUMENTATIONS_AVAILABLE = False

from core.phase1_sar.preprocessing import (
    MIN_SPILL_FRAC,
    PADDING_PX,
    TARGET_SIZE,
    check_spill_fraction,
    crop_and_resize,
    find_spill_bounding_box,
)

log = logging.getLogger(__name__)


def get_default_train_augmentations() -> Any:
    """
    Standard SAR-tailored augmentations.
    SAR backscatter is orientation-invariant, making 90-degree rotations,
    horizontal and vertical flips physically valid.
    """
    if not ALBUMENTATIONS_AVAILABLE:
        return None

    return A.Compose([
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.ShiftScaleRotate(shift_limit=0.05, scale_limit=0.1, rotate_limit=15, p=0.4),
        A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=0.3),
        ToTensorV2(),
    ])


def get_default_val_augmentations() -> Any:
    if not ALBUMENTATIONS_AVAILABLE:
        return None
    return A.Compose([
        ToTensorV2(),
    ])


class SAROilSpillDataset(Dataset):
    """
    PyTorch Dataset loading preprocessed 256x256 SAR image and mask pairs.
    """

    def __init__(
        self,
        images_dir: Union[str, Path],
        masks_dir: Union[str, Path],
        file_list: Optional[List[str]] = None,
        transform: Optional[Callable] = None,
    ):
        self.images_dir = Path(images_dir)
        self.masks_dir = Path(masks_dir)
        self.transform = transform

        if file_list is not None:
            self.filenames = [
                f for f in file_list
                if (self.images_dir / f).exists() and (self.masks_dir / f).exists()
            ]
        else:
            image_files = set(os.listdir(self.images_dir))
            mask_files = set(os.listdir(self.masks_dir))
            self.filenames = sorted(list(image_files.intersection(mask_files)))

        log.info("Initialized SAROilSpillDataset with %d verified pairs", len(self.filenames))

    def __len__(self) -> int:
        return len(self.filenames)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        fname = self.filenames[idx]
        img_path = self.images_dir / fname
        msk_path = self.masks_dir / fname

        img = np.array(Image.open(img_path).convert("L"), dtype=np.uint8)
        msk = np.array(Image.open(msk_path).convert("L"), dtype=np.uint8)
        # Binarize mask to 0/1
        msk_binary = (msk > 127).astype(np.float32)

        if self.transform is not None:
            augmented = self.transform(image=img, mask=msk_binary)
            img_t = augmented["image"].float() / 255.0
            msk_t = augmented["mask"]
            if msk_t.ndim == 2:
                msk_t = msk_t.unsqueeze(0)
            msk_t = msk_t.float()
        else:
            img_t = torch.from_numpy(img).unsqueeze(0).float() / 255.0
            msk_t = torch.from_numpy(msk_binary).unsqueeze(0).float()

        return img_t, msk_t


def preprocess_tile_around_spill(
    raw_img_path: Union[str, Path],
    raw_msk_path: Union[str, Path],
    out_img_path: Union[str, Path],
    out_msk_path: Union[str, Path],
    padding: int = PADDING_PX,
    min_spill_frac: float = MIN_SPILL_FRAC,
) -> bool:
    """
    Process one raw tile according to the Phase 1 preprocessing specification:
    1. Count oil pixels (mask > 127) -> skip if 0.
    2. Find bounding box of oil pixels.
    3. Add 32-pixel padding.
    4. Crop image and mask to region.
    5. Resize to 256x256.
    6. Verify >= 5% oil fraction -> skip if weak.
    7. Save cropped tile.

    Returns:
        True if successfully saved, False if skipped.
    """
    msk = np.array(Image.open(raw_msk_path).convert("L"))
    oil_mask = msk > 127
    if oil_mask.sum() == 0:
        return False

    bbox = find_spill_bounding_box(msk, padding=padding, threshold=127)
    if bbox is None:
        return False

    img = np.array(Image.open(raw_img_path).convert("L"))

    # Crop and resize
    crop_img = crop_and_resize(img, bbox, target_size=TARGET_SIZE)
    crop_msk = crop_and_resize(msk, bbox, target_size=TARGET_SIZE)

    # Verify minimum spill fraction
    valid, frac = check_spill_fraction(crop_msk, min_fraction=min_spill_frac, threshold=127)
    if not valid:
        return False

    # Save
    Path(out_img_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_msk_path).parent.mkdir(parents=True, exist_ok=True)

    Image.fromarray((crop_img * 255.0).astype(np.uint8) if crop_img.dtype != np.uint8 else crop_img).save(out_img_path)
    Image.fromarray((crop_msk > 127).astype(np.uint8) * 255).save(out_msk_path)
    return True
