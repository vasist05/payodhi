"""
Dataset loader for SAR False-Positive Filtering with auxiliary wind vector channels (SAR-UV).
Supports 1-channel (SAR only), 2-channel (SAR + wind speed), and 3-channel (SAR + U10 + V10) modes.
"""

import json
import os
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import torchvision.transforms as T


class SpillFilterDataset(Dataset):
    """
    PyTorch Dataset for CSIRO SAR oil spill vs lookalike classification.
    Constructs multi-channel tensors combining SAR backscatter and ERA5 wind fields.
    """

    def __init__(
        self,
        patch_dir: Union[str, Path] = "data/fp_filter/csiro_patches",
        metadata_file: Union[str, Path] = "data/fp_filter/wind_metadata.json",
        file_list: Optional[List[str]] = None,
        img_size: int = 224,
        mode: str = "sar_uv",  # 'sar_uv' (3-ch), 'sar_speed' (2-ch), 'sar_only' (1-ch), 'sar_4ch' (4-ch)
        is_training: bool = True,
        return_dict: bool = False,
    ):
        self.patch_dir = Path(patch_dir)
        self.img_size = img_size
        self.mode = mode
        self.is_training = is_training
        self.return_dict = return_dict

        # Load metadata
        with open(metadata_file, "r", encoding="utf-8") as f:
            self.metadata: Dict[str, dict] = json.load(f)

        if file_list is not None:
            self.samples = [f for f in file_list if f in self.metadata]
        else:
            self.samples = list(self.metadata.keys())

        # SAR Image Augmentations
        if is_training:
            self.sar_transforms = T.Compose([
                T.Resize((img_size, img_size)),
                T.RandomHorizontalFlip(p=0.5),
                T.RandomVerticalFlip(p=0.5),
                T.ToTensor(),  # [1, H, W] in range [0, 1]
            ])
        else:
            self.sar_transforms = T.Compose([
                T.Resize((img_size, img_size)),
                T.ToTensor(),
            ])

    def __len__(self) -> int:
        return len(self.samples)

    def _get_wind_vectors(self, filename: str, meta: dict) -> Tuple[float, float]:
        """Return real ERA5 U10/V10 (m/s) for this patch from pre-joined metadata."""
        u10 = meta.get("u10")
        v10 = meta.get("v10")
        if u10 is None or v10 is None:
            raise KeyError(
                f"ERA5 wind missing for {filename}. "
                f"Run scripts/download_era5_batched.py then scripts/join_era5_metadata.py."
            )
        return float(u10), float(v10)

    def __getitem__(self, idx: int) -> Union[Tuple[torch.Tensor, torch.Tensor, str], Dict[str, Any]]:
        filename = self.samples[idx]
        meta = self.metadata[filename]
        category = meta["category"]
        label = float(meta["label"])

        # Locate image file
        img_path = self.patch_dir / category / filename
        if not img_path.exists():
            # Fallback search
            alt_path = self.patch_dir / filename
            if alt_path.exists():
                img_path = alt_path
            else:
                raise FileNotFoundError(f"Image patch not found: {img_path}")

        # 1. Load SAR patch (Grayscale)
        with Image.open(img_path) as img:
            sar_img = img.convert("L")
            sar_tensor = self.sar_transforms(sar_img)  # Shape: [1, H, W], normalized 0-1

        # 2. Get Wind U10 and V10 vectors
        u10, v10 = self._get_wind_vectors(filename, meta)

        # Normalize wind to [-1, 1] relative to nominal max marine wind ~25 m/s
        u10_norm = np.clip(u10 / 25.0, -1.0, 1.0)
        v10_norm = np.clip(v10 / 25.0, -1.0, 1.0)
        wind_speed = math.sqrt(u10**2 + v10**2)
        wind_speed_norm = np.clip(wind_speed / 25.0, 0.0, 1.0)

        # 3. Stack channels based on selected mode
        h, w = self.img_size, self.img_size

        if self.mode == "sar_only":
            # 1-Channel: SAR
            input_tensor = sar_tensor  # [1, H, W]

        elif self.mode == "sar_speed":
            # 2-Channel: SAR + Wind Speed
            speed_channel = torch.full((1, h, w), float(wind_speed_norm), dtype=torch.float32)
            input_tensor = torch.cat([sar_tensor, speed_channel], dim=0)  # [2, H, W]

        elif self.mode in ("sar_4ch", "sar_uv_speed", "sar_uv_radiometry"):
            # 4-Channel: SAR + U10 + V10 + Wind Speed
            u_channel = torch.full((1, h, w), float(u10_norm), dtype=torch.float32)
            v_channel = torch.full((1, h, w), float(v10_norm), dtype=torch.float32)
            speed_channel = torch.full((1, h, w), float(wind_speed_norm), dtype=torch.float32)
            input_tensor = torch.cat([sar_tensor, u_channel, v_channel, speed_channel], dim=0)  # [4, H, W]

        else:
            # 3-Channel: SAR + U10 + V10 (SAR-UV)
            u_channel = torch.full((1, h, w), float(u10_norm), dtype=torch.float32)
            v_channel = torch.full((1, h, w), float(v10_norm), dtype=torch.float32)
            input_tensor = torch.cat([sar_tensor, u_channel, v_channel], dim=0)  # [3, H, W]

        target = torch.tensor(label, dtype=torch.float32)
        return {
            "image": input_tensor,
            "label": target,
            "filename": filename,
            "u10": float(u10),
            "v10": float(v10),
        }


def create_dataloaders(
    patch_dir: str = "data/fp_filter/csiro_patches",
    metadata_file: str = "data/fp_filter/wind_metadata.json",
    batch_size: int = 32,
    img_size: int = 224,
    mode: str = "sar_uv",
    val_split: float = 0.2,
    seed: int = 42,
    num_workers: int = 0,
) -> Tuple[DataLoader, DataLoader, List[str], List[str]]:
    """
    Creates stratified Train and Validation DataLoaders.
    """
    with open(metadata_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    oil_files = [k for k, v in meta.items() if v["label"] == 1]
    non_oil_files = [k for k, v in meta.items() if v["label"] == 0]

    np.random.seed(seed)
    np.random.shuffle(oil_files)
    np.random.shuffle(non_oil_files)

    n_oil_val = int(len(oil_files) * val_split)
    n_non_oil_val = int(len(non_oil_files) * val_split)

    val_files = oil_files[:n_oil_val] + non_oil_files[:n_non_oil_val]
    train_files = oil_files[n_oil_val:] + non_oil_files[n_non_oil_val:]

    np.random.shuffle(train_files)
    np.random.shuffle(val_files)

    train_dataset = SpillFilterDataset(
        patch_dir=patch_dir,
        metadata_file=metadata_file,
        file_list=train_files,
        img_size=img_size,
        mode=mode,
        is_training=True,
    )

    val_dataset = SpillFilterDataset(
        patch_dir=patch_dir,
        metadata_file=metadata_file,
        file_list=val_files,
        img_size=img_size,
        mode=mode,
        is_training=False,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True if torch.cuda.is_available() else False,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True if torch.cuda.is_available() else False,
    )

    return train_loader, val_loader, train_files, val_files
