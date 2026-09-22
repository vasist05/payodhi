"""
Evaluation & Ablation Study Engine for Phase 2.
Compares 1-channel (SAR only), 2-channel (SAR + wind speed), and 3-channel (SAR-UV) configurations.
"""

import argparse
import json
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn

from core.phase2_false_positive.dataset import create_dataloaders
from core.phase2_false_positive.model import build_model
from core.phase2_false_positive.train import calculate_metrics, evaluate_epoch


def expected_calibration_error(probs, labels, n_bins=15):
    """
    Expected Calibration Error. Lower is better. Target: <= 0.05.
    probs: array-like of predicted probabilities in [0, 1]
    labels: array-like of ground truth {0, 1}
    """
    probs = np.asarray(probs, dtype=np.float64).ravel()
    labels = np.asarray(labels, dtype=np.float64).ravel()
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(probs)
    for lo, hi in zip(bins[:-1], bins[1:]):
        if hi == 1.0:
            mask = (probs >= lo) & (probs <= hi)
        else:
            mask = (probs >= lo) & (probs < hi)
        if mask.sum() == 0:
            continue
        conf = probs[mask].mean()
        acc = labels[mask].mean()
        ece += (mask.sum() / n) * abs(conf - acc)
    return float(ece)


def evaluate_checkpoint(checkpoint_path: str, mode: str = "sar_uv", val_split: float = 0.2):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading checkpoint: {checkpoint_path} on {device}")

    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = build_model(mode=mode, pretrained=False).to(device)
    state_dict = ckpt.get("state_dict", ckpt.get("model_state_dict", ckpt))
    model.load_state_dict(state_dict)
    T = float(ckpt.get("temperature", 1.0))
    model.eval()

    _, val_loader, _, _ = create_dataloaders(
        patch_dir="data/fp_filter/csiro_patches",
        metadata_file="data/fp_filter/wind_metadata.json",
        batch_size=32,
        mode=mode,
        val_split=val_split,
        seed=42,
    )

    criterion = nn.BCEWithLogitsLoss()
    metrics = evaluate_epoch(model, val_loader, criterion, device)

    # Retrieve honest ECE stored in the checkpoint (fit on disjoint data)
    honest_ece = ckpt.get("ece", None)
    if honest_ece is None:
        raise RuntimeError(
            f"Checkpoint at {checkpoint_path} has no calibrated 'ece'. "
            f"Run scripts/run_ablation_study.py to fit temperature and compute honest held-out ECE."
        )

    print(f"[{mode}] ECE = {honest_ece:.4f} (honest, held-out)")
    metrics["ece"] = honest_ece
    metrics["temperature"] = T
    return metrics


def print_metrics_table(results: dict):
    print("\n" + "=" * 80)
    print("      FALSE-POSITIVE FILTER ABLATION & BENCHMARK STUDY RESULTS")
    print("=" * 80)
    print(f"{'Model Configuration':<25} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'FPR (%)':<10} | {'ECE':<8}")
    print("-" * 80)

    for name, m in results.items():
        ece_str = f"{m.get('ece', float('nan')):.4f}" if "ece" in m else "N/A"
        print(
            f"{name:<25} | "
            f"{m['precision']*100:>8.2f}% | "
            f"{m['recall']*100:>8.2f}% | "
            f"{m['f1']*100:>8.2f}% | "
            f"{m['fpr']*100:>8.2f}% | "
            f"{ece_str:>8}"
        )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate SpillFilterNet")
    parser.add_argument("--checkpoint", type=str, required=False, default="core/phase2_false_positive/checkpoints/best_model_sar_uv.pth")
    parser.add_argument("--mode", type=str, default="sar_uv")
    args = parser.parse_args()

    if Path(args.checkpoint).exists():
        metrics = evaluate_checkpoint(args.checkpoint, mode=args.mode)
        print_metrics_table({f"SpillFilterNet ({args.mode})": metrics})
    else:
        print(f"Checkpoint {args.checkpoint} not found. Run training first.")
