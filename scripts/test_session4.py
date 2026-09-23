import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import glob
from core.phase3_drift.drift_model.aggregate import (
    build_heatmap, confidence_contours, peak_location, contour_to_polygon,
)

files = glob.glob("data/ensemble_outputs/bwd_*.nc")
print(f"Found {len(files)} NetCDF file(s)")

if not files:
    print("No files yet - run Session 3 first")
else:
    H, lon_bins, lat_bins = build_heatmap(
        files,
        lon_bounds=(71.5, 73.5),
        lat_bounds=(20.5, 21.5),
    )
    print(f"Heatmap shape: {H.shape}")
    print(f"Heatmap sum:   {H.sum():.4f}  (should be 1.0)")

    contours = confidence_contours(H)
    for lvl, mask in contours.items():
        print(f"  {int(lvl*100)}% contour: {mask.sum()} cells")

    peak = peak_location(H, lon_bins, lat_bins)
    print(f"Peak origin: ({peak['lon']:.3f}, {peak['lat']:.3f}) "
          f"prob={peak['prob']:.4f}")

    poly = contour_to_polygon(contours[0.75], lon_bins, lat_bins)
    print(f"75% polygon (bbox): {poly}")

print()
print("Session 4 OK")
