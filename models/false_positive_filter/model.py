"""
Neural Network Architecture for False-Positive Spill Filtering (SpillFilterNet).
Implements a multi-channel CNN backbone (ResNet-18) tailored for SAR-UV inputs.
"""

import torch
import torch.nn as nn
import torchvision.models as models


class SpillFilterNet(nn.Module):
    """
    Binary classifier distinguishing true oil spills (Class 1) from lookalikes/clean sea (Class 0).
    Configurable to accept 1, 2, or 3 input channels.
    """

    def __init__(
        self,
        in_channels: int = 3,
        pretrained: bool = True,
        dropout_rate: float = 0.3,
        backbone: str = "resnet18",
    ):
        super().__init__()
        self.in_channels = in_channels
        self.backbone_name = backbone

        if backbone == "resnet18":
            weights = models.ResNet18_Weights.DEFAULT if pretrained else None
            base_model = models.resnet18(weights=weights)
        elif backbone == "resnet34":
            weights = models.ResNet34_Weights.DEFAULT if pretrained else None
            base_model = models.resnet34(weights=weights)
        else:
            raise ValueError(f"Unsupported backbone: {backbone}")

        # Modify first conv layer to support arbitrary in_channels (1, 2, 3, 4, etc.)
        if in_channels != 3 or not pretrained:
            old_conv = base_model.conv1
            new_conv = nn.Conv2d(
                in_channels=in_channels,
                out_channels=old_conv.out_channels,
                kernel_size=old_conv.kernel_size,
                stride=old_conv.stride,
                padding=old_conv.padding,
                bias=False,
            )

            # Initialize weights from pretrained RGB filters (handles 1..N channels)
            if pretrained:
                k = min(in_channels, 3)
                new_conv.weight.data[:, :k, :, :] = old_conv.weight.data[:, :k, :, :]
                if in_channels == 1:
                    new_conv.weight.data = old_conv.weight.data.mean(dim=1, keepdim=True)
                elif in_channels > 3:
                    mean_rgb = old_conv.weight.data.mean(dim=1, keepdim=True)
                    for c in range(3, in_channels):
                        new_conv.weight.data[:, c:c + 1, :, :] = mean_rgb
            base_model.conv1 = new_conv

        num_features = base_model.fc.in_features

        # Replace classification head
        base_model.fc = nn.Sequential(
            nn.Dropout(p=dropout_rate),
            nn.Linear(num_features, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout_rate / 2),
            nn.Linear(128, 1),
        )

        self.model = base_model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Returns raw logits: shape [B, 1] or [B]
        """
        logits = self.model(x)
        return logits.squeeze(-1)

    @torch.no_grad()
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """
        Returns probabilities in [0.0, 1.0] for true oil spill class.
        """
        self.eval()
        logits = self.forward(x)
        probs = torch.sigmoid(logits)
        return probs


def build_model(mode: str = "sar_uv", pretrained: bool = True) -> SpillFilterNet:
    if mode == "sar_only":
        in_channels = 1
    elif mode == "sar_speed":
        in_channels = 2
    elif mode == "sar_uv":
        in_channels = 3
    elif mode in ("sar_uv_radiometry", "sar_4ch", "sar_uv_speed"):
        in_channels = 4
    else:
        raise ValueError(f"Unknown mode: {mode}")
    return SpillFilterNet(in_channels=in_channels, pretrained=pretrained)
