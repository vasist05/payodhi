"""
core/phase1_sar/train.py

Training script for Phase 1 SAR Oil Spill Segmentation U-Net.
Implements the exact training strategy:
- Compound Loss: 0.4 * DiceLoss + 0.6 * BCEWithLogitsLoss(pos_weight=3.0)
- Optimizer: Adam (lr=1e-4)
- Scheduler: CosineAnnealingWarmRestarts (T_0=15)
- Freeze encoder for first 3 epochs, unfreeze at 0.5 * lr
- Metrics: IoU, F1-Score
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from core.phase1_sar.dataset import (
    SAROilSpillDataset,
    get_default_train_augmentations,
    get_default_val_augmentations,
)
from core.phase1_sar.model import SARUNetDetector

log = logging.getLogger(__name__)


class CompoundDiceBCELoss(nn.Module):
    """
    Loss = 0.4 * DiceLoss + 0.6 * BCEWithLogitsLoss(pos_weight=3.0)
    Penalizes missing oil pixels 3x more than missing background,
    while Dice Loss directly optimizes IoU/F1 overlap.
    """

    def __init__(self, dice_weight: float = 0.4, bce_weight: float = 0.6, pos_weight: float = 3.0):
        super().__init__()
        self.dice_weight = dice_weight
        self.bce_weight = bce_weight
        self.bce = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight]))

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce_loss = self.bce(logits, targets)

        # Soft Dice Loss
        probs = torch.sigmoid(logits)
        smooth = 1.0
        intersection = (probs * targets).sum(dim=(-2, -1))
        union = probs.sum(dim=(-2, -1)) + targets.sum(dim=(-2, -1))
        dice_loss = 1.0 - (2.0 * intersection + smooth) / (union + smooth)
        dice_loss = dice_loss.mean()

        return self.dice_weight * dice_loss + self.bce_weight * bce_loss


def calculate_metrics(preds: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5) -> Tuple[float, float]:
    """Calculate IoU and F1-Score."""
    pred_binary = (preds > threshold).float()
    intersection = (pred_binary * targets).sum().item()
    total_pred = pred_binary.sum().item()
    total_target = targets.sum().item()
    union = total_pred + total_target - intersection

    iou = (intersection + 1e-6) / (union + 1e-6)
    f1 = (2.0 * intersection + 1e-6) / (total_pred + total_target + 1e-6)
    return float(iou), float(f1)


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    for imgs, masks in loader:
        imgs, masks = imgs.to(device), masks.to(device)
        optimizer.zero_grad()
        logits = model(imgs)
        loss = criterion(logits, masks)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(loader)


@torch.no_grad()
def validate(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> Tuple[float, float]:
    model.eval()
    ious, f1s = [], []
    for imgs, masks in loader:
        imgs, masks = imgs.to(device), masks.to(device)
        probs = torch.sigmoid(model(imgs))
        iou, f1 = calculate_metrics(probs, masks)
        ious.append(iou)
        f1s.append(f1)
    return float(np.mean(ious)), float(np.mean(f1s))
