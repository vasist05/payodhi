import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
from datetime import datetime, timezone

if __name__ == "__main__":
    from core.phase3_drift.drift_model.sampler import sample_scenarios
    from core.phase3_drift.drift_model.orchestrate import full_backward_pipeline
    from core.phase3_drift.drift_model.aggregate import contour_to_polygon
    from core.phase3_drift.drift_model.forcing import (
        make_synthetic_wind, make_synthetic_current
    )
    from adapters.read_spills import read_spill

    # Load detection from mock DB
    spill = read_spill("22222222-2222-2222-2222-222222222222")
    det_lon = spill["detection_lon"]
    det_lat = spill["detection_lat"]
    det_time = spill["detection_time"]

    print(f"Spill: {spill['spill_id']}")
    print(f"  Detection:  ({det_lon}, {det_lat}) at {det_time}")

    # Generate synthetic forcing once
    wind_path = make_synthetic_wind("data/forcing/wind_synthetic.nc")
    current_path = make_synthetic_current("data/forcing/current_synthetic.nc")

    WINDOW_HOURS = 12
    N_RUNS = 100   # keep small for demo speed; scale to 100 in production
    LON_BOUNDS = (71.5, 73.5)
    LAT_BOUNDS = (20.5, 21.5)

    # Sample scenarios
    scenarios = sample_scenarios(
        det_lon, det_lat, det_time,
        window_hours=WINDOW_HOURS, n=N_RUNS,
    )
    print(f"\nRunning backward ensemble: {N_RUNS} scenarios...")

    result = full_backward_pipeline(
        scenarios, wind_path, current_path, None,
        lon_bounds=LON_BOUNDS, lat_bounds=LAT_BOUNDS,
        stokes="wave", n_workers=4,
    )

    peak = result["peak"]
    print(f"\nPeak origin: ({peak['lon']:.3f}, {peak['lat']:.3f})")

    contour_75 = contour_to_polygon(
        result["contours"][0.75],
        result["lon_bins"], result["lat_bins"],
    )

    # Build filter output
    out = {
        "spill_id": spill["spill_id"],
        "filter": {
            "spatial": {
                "contour_75pct": contour_75,
                "bounds": {
                    "lon_min": LON_BOUNDS[0], "lon_max": LON_BOUNDS[1],
                    "lat_min": LAT_BOUNDS[0], "lat_max": LAT_BOUNDS[1],
                },
            },
            "temporal": {
                "release_window_start": (
                    det_time.timestamp() - WINDOW_HOURS * 3600
                ),
                "release_window_end": det_time.timestamp(),
            },
        },
        "peak_origin": peak,
        "ensemble_size": N_RUNS,
        "forcing": {"wind": "ERA5", "current": "CMEMS",
                    "waves": "ERA5", "stokes": "wave"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with open("data/phase3_output.json", "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"\nSaved: data/phase3_output.json")
    print(f"Filter region: 75% contour with {len(contour_75)} corners")
    print(f"Release window: {WINDOW_HOURS} hours before detection")
    print()
    print("Phase 3 complete.")
