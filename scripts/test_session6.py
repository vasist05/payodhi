import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from datetime import datetime, timezone


if __name__ == "__main__":
    from adapters.read_spills import read_spill
    from adapters.read_candidates import read_candidates
    from core.phase3_drift.forward_attribution.scorer import score_vessel
    from core.phase3_drift.forward_attribution.rank import (
        rank_candidates, classify_attribution
    )
    from core.phase3_drift.drift_model.forcing import (
        make_synthetic_wind, make_synthetic_current
    )
    import os
    import glob

    wind_path = make_synthetic_wind("data/forcing/wind_synthetic.nc")
    current_path = make_synthetic_current("data/forcing/current_synthetic.nc")
    print(f"Using wind:    {wind_path}")
    print(f"Using current: {current_path}")
    print()

    spill = read_spill("spill_001")
    det_lon = spill["centroid_lon"]
    det_lat = spill["centroid_lat"]
    det_time = spill["detection_time"]

    win_start = datetime(2024, 6, 15, 2, 0, tzinfo=timezone.utc)
    win_end   = datetime(2024, 6, 15, 14, 0, tzinfo=timezone.utc)
    candidates = read_candidates(win_start, win_end)

    for f in glob.glob("data/forward_outputs/*.nc"):
        try:
            os.remove(f)
        except OSError:
            pass

    scores = []
    for cand in candidates:
        c = {**cand, "detection_time": det_time}
        print(f"--- Forward run for {cand['mmsi']} ---")
        s = score_vessel(
            c, det_lon, det_lat,
            wind=wind_path,
            current=current_path,
            wave=None,
        )
        print(f"  score={s['forward_score']:.3f}  "
              f"dist={s.get('distance_km')}  "
              f"centroid={s.get('predicted_centroid')}  "
              f"error={s.get('error', 'none')}")
        print()
        scores.append(s)

    print("=== NetCDF files produced ===")
    for f in glob.glob("data/forward_outputs/*.nc"):
        import xarray as xr
        import numpy as np
        ds = xr.open_dataset(f)
        lon = ds["lon"].values
        lat = ds["lat"].values
        valid = (~np.isnan(lon)) & (~np.isnan(lat))
        print(f"  {f}: valid particles at last step={valid[:, -1].sum()}")
        ds.close()

    print()
    ranked = rank_candidates(scores)
    outcome = classify_attribution(ranked)

    print("=== Ranked candidates ===")
    for i, r in enumerate(ranked, 1):
        print(f"  {i}. {r['mmsi']} -- {r['vessel_name']}  "
              f"score={r['forward_score']:.3f}  "
              f"dist={r['distance_km']:.1f} km")

    print()
    print(f"Outcome: {outcome['outcome']} â€” {outcome['reason']}")
    print()
    print("Session 6 debug complete")
