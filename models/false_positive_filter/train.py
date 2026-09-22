"""
Training script for SpillFilterNet with SAR-UV inputs.
Includes positive class weighting, LR scheduling, early stopping,
and per-epoch rolling checkpoints (resume-safe).
"""

import argparse
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

from models.false_positive_filter.dataset import create_dataloaders
from models.false_positive_filter.model import build_model


def seed_everything(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def calculate_metrics(y_true, y_pred_prob, threshold=0.5):
    y_true = np.asarray(y_true).ravel()
    y_pred_prob = np.asarray(y_pred_prob).ravel()

    # Guard: single-class batch
    if len(np.unique(y_true)) < 2:
        y_pred = (y_pred_prob >= threshold).astype(int)
        return {
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall":    float(recall_score(y_true, y_pred, zero_division=0)),
            "f1":        float(f1_score(y_true, y_pred, zero_division=0)),
            "fpr":       0.0,
            "auc":       0.5,
            "tp": int(((y_pred == 1) & (y_true == 1)).sum()),
            "fp": int(((y_pred == 1) & (y_true == 0)).sum()),
            "tn": int(((y_pred == 0) & (y_true == 0)).sum()),
            "fn": int(((y_pred == 0) & (y_true == 1)).sum()),
        }

    y_pred = (y_pred_prob >= threshold).astype(int)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall    = recall_score(y_true, y_pred, zero_division=0)
    f1        = f1_score(y_true, y_pred, zero_division=0)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    try:
        auc = roc_auc_score(y_true, y_pred_prob)
    except ValueError:
        auc = 0.5

    return {
        "precision": float(precision),
        "recall":    float(recall),
        "f1":        float(f1),
        "fpr":       float(fpr),
        "auc":       float(auc),
        "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
    }


def train_epoch(model, dataloader, criterion, optimizer, device):
    model.train()
    running_loss = 0.0
    all_targets, all_preds = [], []

    for batch in dataloader:
        if isinstance(batch, dict):
            inputs  = batch["image"].to(device, non_blocking=True)
            targets = batch["label"].to(device, non_blocking=True)
        else:
            inputs, targets, _ = batch
            inputs  = inputs.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)

        optimizer.zero_grad()
        logits = model(inputs)
        loss = criterion(logits, targets)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * inputs.size(0)
        probs = torch.sigmoid(logits).detach().cpu().numpy()
        all_preds.extend(probs)
        all_targets.extend(targets.detach().cpu().numpy())

    epoch_loss = running_loss / len(dataloader.dataset)
    metrics = calculate_metrics(np.array(all_targets), np.array(all_preds))
    metrics["loss"] = epoch_loss
    return metrics


@torch.no_grad()
def evaluate_epoch(model, dataloader, criterion, device):
    model.eval()
    running_loss = 0.0
    all_targets, all_preds = [], []

    for batch in dataloader:
        if isinstance(batch, dict):
            inputs  = batch["image"].to(device, non_blocking=True)
            targets = batch["label"].to(device, non_blocking=True)
        else:
            inputs, targets, _ = batch
            inputs  = inputs.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)

        logits = model(inputs)
        loss = criterion(logits, targets)

        running_loss += loss.item() * inputs.size(0)
        probs = torch.sigmoid(logits).cpu().numpy()
        all_preds.extend(probs)
        all_targets.extend(targets.cpu().numpy())

    val_loss = running_loss / len(dataloader.dataset)
    metrics = calculate_metrics(np.array(all_targets), np.array(all_preds))
    metrics["loss"] = val_loss
    return metrics


def _compute_pos_weight(train_loader, device):
    """Compute BCE pos_weight from actual training labels."""
    ds = getattr(train_loader, "dataset", None)
    if ds is not None and hasattr(ds, "samples") and hasattr(ds, "metadata"):
        pos = sum(1 for f in ds.samples if ds.metadata.get(f, {}).get("label") == 1)
        neg = len(ds.samples) - pos
        if pos == 0:
            return torch.tensor([1.0], device=device)
        return torch.tensor([neg / pos], device=device)

    pos = neg = 0
    for batch in train_loader:
        if isinstance(batch, dict):
            y = batch["label"]
        else:
            _, y, _ = batch
        y = y.view(-1)
        pos += int((y == 1).sum().item())
        neg += int((y == 0).sum().item())
    if pos == 0:
        return torch.tensor([1.0], device=device)
    return torch.tensor([neg / pos], device=device)


def train_pipeline(
    data_dir="data/fp_filter/csiro_patches",
    metadata_file="data/fp_filter/wind_metadata.json",
    checkpoint_dir="models/false_positive_filter/checkpoints",
    epochs=15,
    batch_size=32,
    lr=3e-4,
    mode="sar_uv",
    val_split=0.2,
    seed=42,
    resume=False,
):
    seed_everything(seed)
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Training SpillFilterNet [{mode.upper()}] on {device} ===", flush=True)

    train_loader, val_loader, _, _ = create_dataloaders(
        patch_dir=data_dir,
        metadata_file=metadata_file,
        batch_size=batch_size,
        mode=mode,
        val_split=val_split,
        seed=seed,
    )

    pos_weight = _compute_pos_weight(train_loader, device)
    print(f"[{mode}] pos_weight = {pos_weight.item():.3f}", flush=True)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    model = build_model(mode=mode, pretrained=True).to(device)
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    best_checkpoint_path = Path(checkpoint_dir) / f"best_model_{mode}.pth"
    rolling_checkpoint_path = Path(checkpoint_dir) / f"rolling_{mode}.pth"

    best_val_f1 = 0.0
    start_epoch = 1

    # Resume from rolling checkpoint if requested
    if resume and rolling_checkpoint_path.exists():
        ckpt = torch.load(rolling_checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["state_dict"])
        optimizer.load_state_dict(ckpt["optimizer"])
        scheduler.load_state_dict(ckpt["scheduler"])
        best_val_f1 = ckpt.get("best_f1", 0.0)
        start_epoch = ckpt["epoch"] + 1
        print(f"[{mode}] Resumed from epoch {ckpt['epoch']} (best F1={best_val_f1:.4f})", flush=True)

    for epoch in range(start_epoch, epochs + 1):
        t0 = time.time()
        train_m = train_epoch(model, train_loader, criterion, optimizer, device)
        val_m = evaluate_epoch(model, val_loader, criterion, device)
        scheduler.step()
        elapsed = time.time() - t0

        print(
            f"Epoch [{epoch:02d}/{epochs:02d}] ({elapsed:.1f}s) | "
            f"Train Loss: {train_m['loss']:.4f}, F1: {train_m['f1']:.3f} | "
            f"Val Loss: {val_m['loss']:.4f}, Prec: {val_m['precision']:.3f}, "
            f"Rec: {val_m['recall']:.3f}, F1: {val_m['f1']:.3f}, FPR: {val_m['fpr']*100:.2f}%",
            flush=True,
        )

        # Always write rolling checkpoint (so Colab sync + resume work)
        torch.save({
            "epoch": epoch,
            "state_dict": model.state_dict(),
            "optimizer":  optimizer.state_dict(),
            "scheduler":  scheduler.state_dict(),
            "best_f1":    best_val_f1,
            "mode":       mode,
            "val_metrics": val_m,
        }, rolling_checkpoint_path)

        # Save best-so-far too
        if val_m["f1"] > best_val_f1:
            best_val_f1 = val_m["f1"]
            torch.save({
                "epoch": epoch,
                "state_dict": model.state_dict(),
                "best_f1": best_val_f1,
                "mode": mode,
                "val_metrics": val_m,
            }, best_checkpoint_path)
            print(f"  -> Saved new best checkpoint (F1={best_val_f1:.4f})", flush=True)

    print(f"\n[{mode}] Training complete. Best Val F1: {best_val_f1:.4f}", flush=True)
    return str(best_checkpoint_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train SpillFilterNet")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--mode", choices=["sar_only", "sar_speed", "sar_uv"], default="sar_uv")
    parser.add_argument("--resume", action="store_true", help="Resume from rolling checkpoint")
    args = parser.parse_args()

    train_pipeline(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        mode=args.mode,
        resume=args.resume,
    )
