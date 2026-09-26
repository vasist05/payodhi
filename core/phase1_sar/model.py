"""
core/phase1_sar/model.py

PyTorch U-Net model architecture for SAR Oil Spill Segmentation (Phase 1).
Configured with a ResNet-34 encoder, 1 input channel (SAR grayscale VV backscatter),
and 1 output class (binary oil spill mask).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import torch
import torch.nn as nn

try:
    import segmentation_models_pytorch as smp
    SMP_AVAILABLE = True
except ImportError:
    SMP_AVAILABLE = False

log = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_PATH = Path("base_model_kaggle_iou7441.pth")


class SARUNetDetector(nn.Module):
    """
    U-Net segmentation model for SAR oil spill detection.
    Default architecture: ResNet-34 backbone with ImageNet pretrained encoder,
    single-channel grayscale input, and sigmoid output probability.
    """

    def __init__(
        self,
        encoder_name: str = "resnet34",
        encoder_weights: Optional[str] = "imagenet",
        in_channels: int = 1,
        classes: int = 1,
    ):
        super().__init__()
        if not SMP_AVAILABLE:
            raise ImportError(
                "segmentation_models_pytorch is required for SARUNetDetector. "
                "Install via: pip install segmentation-models-pytorch"
            )

        try:
            self.model = smp.Unet(
                encoder_name=encoder_name,
                encoder_weights=encoder_weights,
                in_channels=in_channels,
                classes=classes,
            )
        except Exception as exc:
            log.warning("Could not download pretrained weights (%s), initializing without ImageNet weights: %s", encoder_weights, exc)
            self.model = smp.Unet(
                encoder_name=encoder_name,
                encoder_weights=None,
                in_channels=in_channels,
                classes=classes,
            )
        self.encoder_name = encoder_name
        self.in_channels = in_channels
        self.classes = classes

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass returning raw logits: shape [B, 1, H, W].
        """
        return self.model(x)

    @torch.no_grad()
    def predict_mask(
        self,
        x: torch.Tensor,
        threshold: float = 0.5,
    ) -> torch.Tensor:
        """
        Return binary mask (0 or 1) given threshold: shape [B, 1, H, W].
        """
        self.eval()
        probs = self.predict_proba(x)
        return (probs > threshold).float()

    @torch.no_grad()
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """
        Return probability tensor in [0.0, 1.0]: shape [B, 1, H, W].
        """
        self.eval()
        logits = self.forward(x)
        return torch.sigmoid(logits)


def build_model(
    encoder_name: str = "resnet34",
    in_channels: int = 1,
    classes: int = 1,
) -> SARUNetDetector:
    """Build uninitialized or pretrained backbone model."""
    return SARUNetDetector(
        encoder_name=encoder_name,
        encoder_weights=None,
        in_channels=in_channels,
        classes=classes,
    )


def load_detection_model(
    checkpoint_path: Optional[Union[str, Path]] = None,
    device: Optional[Union[str, torch.device]] = None,
) -> SARUNetDetector:
    """
    Load trained Phase 1 U-Net model from checkpoint (e.g. base_model_kaggle_iou7441.pth).

    Supports:
      - dict with 'model_state_dict' (standard trainer output)
      - raw state_dict
      - direct model weights
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    elif isinstance(device, str):
        device = torch.device(device)

    path = Path(checkpoint_path) if checkpoint_path else DEFAULT_CHECKPOINT_PATH

    if not path.is_file():
        # Check parent and root directories
        search_candidates = [
            path,
            Path.cwd() / path.name,
            Path("models/detection/checkpoints") / path.name,
            Path("core/phase1_sar/checkpoints") / path.name,
        ]
        found = None
        for cand in search_candidates:
            if cand.is_file():
                found = cand
                break
        if found is None:
            raise FileNotFoundError(
                f"Checkpoint not found at '{path}'. Checked candidates: {search_candidates}"
            )
        path = found

    log.info("Loading Phase 1 detection model from: %s on device: %s", path, device)
    model = build_model(encoder_name="resnet34", in_channels=1, classes=1)

    ckpt = torch.load(path, map_location=device, weights_only=False)
    if isinstance(ckpt, dict) and "model_state_dict" in ckpt:
        state_dict = ckpt["model_state_dict"]
        epoch = ckpt.get("epoch")
        best_iou = ckpt.get("best_iou")
        log.info("Loaded checkpoint metadata: epoch=%s, best_iou=%s", epoch, best_iou)
    elif isinstance(ckpt, dict):
        state_dict = ckpt
    else:
        state_dict = ckpt.state_dict()

    # Strip potential 'module.' prefix from DataParallel training
    clean_state_dict = {}
    for k, v in state_dict.items():
        if k.startswith("module."):
            clean_state_dict[k[7:]] = v
        elif k.startswith("model."):
            clean_state_dict[k[6:]] = v
        else:
            clean_state_dict[k] = v

    model.model.load_state_dict(clean_state_dict)
    model.to(device)
    model.eval()
    log.info("Phase 1 SAR U-Net detector loaded successfully.")
    return model
