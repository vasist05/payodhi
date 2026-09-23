"""Generate heatmap PNG + save .npy from the ensemble outputs (zoomed)."""
import glob
import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

if __name__ == "__main__":
    from core.phase3_drift.drift_model.aggregate import (
        build_heatmap, confidence_contours, peak_location,
    )

    files = glob.glob("data/ensemble_outputs/bwd_*.nc")
    print(f"Found {len(files)} ensemble files")
    if not files:
        print("No ensemble files. Run scripts.run_phase3 first.")
        raise SystemExit(1)

    # ── Build heatmap over a WIDER area first ──────────────
    H, lon_bins, lat_bins = build_heatmap(
        files,
        lon_bounds=(71.5, 73.5),
        lat_bounds=(20.5, 21.5),
        resolution=0.01,          # finer grid = crisper zoom
    )
    print(f"Heatmap shape: {H.shape}  sum: {H.sum():.4f}")

    contours = confidence_contours(H, levels=(0.5, 0.75, 0.9))
    peak = peak_location(H, lon_bins, lat_bins)
    print(f"Peak origin: ({peak['lon']:.3f}, {peak['lat']:.3f})")

    # Save raw arrays
    np.save("data/heatmap.npy", H)
    np.save("data/lon_bins.npy", lon_bins)
    np.save("data/lat_bins.npy", lat_bins)

    # ── Zoom window: crop the view around the peak ─────────
    # Pick a window size in degrees — 0.4° ≈ 40 km wide
    ZOOM_DEG = 0.4
    lon_min = peak["lon"] - ZOOM_DEG / 2
    lon_max = peak["lon"] + ZOOM_DEG / 2
    lat_min = peak["lat"] - ZOOM_DEG / 2
    lat_max = peak["lat"] + ZOOM_DEG / 2

    print(f"Zoom window: lon [{lon_min:.3f}, {lon_max:.3f}]  "
          f"lat [{lat_min:.3f}, {lat_max:.3f}]")

    # ── Plot ───────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 10), dpi=120)

    lon_c = (lon_bins[:-1] + lon_bins[1:]) / 2
    lat_c = (lat_bins[:-1] + lat_bins[1:]) / 2

    cmap = LinearSegmentedColormap.from_list(
        "oilspill", ["#ffffff", "#ffe066", "#ff8800", "#cc0000"]
    )

    mesh = ax.pcolormesh(lon_bins, lat_bins, H, cmap=cmap, shading="auto")

    # Contours
    for lvl, color in zip((0.9, 0.75, 0.5), ("#333333", "#666666", "#999999")):
        mask = contours[lvl].astype(float)
        ax.contour(
            lon_c, lat_c, mask,
            levels=[0.5], colors=color, linewidths=2.0,
            linestyles="--",
        )
        # Label the contour with its level
        ax.text(peak["lon"] + 0.01, lat_min + 0.02 * (1 - lvl),
                f"{int(lvl*100)}% contour",
                fontsize=9, color=color)

    # Peak marker
    ax.plot(peak["lon"], peak["lat"], "*",
            color="black", markersize=22, markeredgecolor="white",
            markeredgewidth=1.5,
            label=f"Peak origin  ({peak['lon']:.3f}, {peak['lat']:.3f})")

    # Detection point
    ax.plot(72.5, 21.0, "X", color="blue", markersize=16,
            markeredgecolor="white", markeredgewidth=1.5,
            label="Detection point  (72.500, 21.000)")

    # Draw a small circle showing the zoom box
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)

    ax.set_xlabel("Longitude (°E)", fontsize=11)
    ax.set_ylabel("Latitude (°N)", fontsize=11)
    ax.set_title(
        f"Origin probability heatmap — zoomed to peak\n"
        f"(100-run Monte Carlo backward ensemble)",
        fontsize=12,
    )
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(alpha=0.3)
    plt.colorbar(mesh, ax=ax, label="Probability density", shrink=0.8)
    plt.tight_layout()

    os.makedirs("data/demo_cache", exist_ok=True)
    out = "data/demo_cache/heatmap_zoomed.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    print(f"Saved: {out}")

    out_hi = "data/demo_cache/heatmap_zoomed_hires.png"
    plt.savefig(out_hi, dpi=300, bbox_inches="tight")
    print(f"Saved: {out_hi}")

    plt.show()