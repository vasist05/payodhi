import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
from datetime import datetime, timezone

if __name__ == "__main__":
    from adapters.read_spills import read_spill
    from adapters.read_candidates import read_candidates
    from adapters.write_drift_runs import write_drift_run
    from core.phase3_drift.forward_attribution.scorer import score_vessel
    from core.phase3_drift.forward_attribution.rank import (
        rank_candidates, classify_attribution
    )
    from core.phase3_drift.drift_model.forcing import (
        make_synthetic_wind, make_synthetic_current
    )

    # Load Phase 3 filter output
    with open("data/phase3_output.json") as f:
        phase3 = json.load(f)

    # Load detection
    spill = read_spill("22222222-2222-2222-2222-222222222222")
    det_lon = spill["detection_lon"]
    det_lat = spill["detection_lat"]
    det_time = spill["detection_time"]

    # Generate synthetic forcing once
    wind_path = make_synthetic_wind("data/forcing/wind_synthetic.nc")
    current_path = make_synthetic_current("data/forcing/current_synthetic.nc")

    # Read candidates from release window
    win_start = datetime.fromtimestamp(
        phase3["filter"]["temporal"]["release_window_start"], tz=timezone.utc
    )
    win_end = datetime.fromtimestamp(
        phase3["filter"]["temporal"]["release_window_end"], tz=timezone.utc
    )
    candidates = read_candidates(win_start, win_end)

    print(f"Scoring {len(candidates)} candidates from forward simulations...")
    print()

    scores = []
    for cand in candidates:
        c = {**cand, "detection_time": det_time}
        s = score_vessel(
            c, det_lon, det_lat,
            wind=wind_path, current=current_path, wave=None,
        )
        scores.append(s)

        # Write each forward run to drift_runs (mock DB)
        write_drift_run({
            "spill_id": spill["spill_id"],
            "scene_id": spill["scene_id"], 
            "vessel_mmsi": s["mmsi"],
            "vessel_id": c.get("vessel_id"), 
            "mode": "forward",
            "oil_type_sampled": c["oil_type"],
            "release_time": str(c["release_time"]),
            "detection_time": str(det_time),
            "predicted_lon": (s["predicted_centroid"][0]
                              if s.get("predicted_centroid") else None),
            "predicted_lat": (s["predicted_centroid"][1]
                              if s.get("predicted_centroid") else None),
            "distance_km": s.get("distance_km"),
            "forward_score": s["forward_score"],
        })

        d = s.get("distance_km")
        d_str = f"{d:.1f} km" if d is not None else "n/a"
        print(f"  {s['mmsi']}: score={s['forward_score']:.3f}  dist={d_str}")

    # Rank
    ranked = rank_candidates(scores)
    outcome = classify_attribution(ranked)

    # Save attribution summary
    summary = {
        "spill_id": spill["spill_id"],
        "ranked_candidates": ranked,
        "attribution_outcome": outcome,
        "n_candidates": len(ranked),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with open("data/forward_attribution.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print()
    print("=== Ranked candidates ===")
    for i, r in enumerate(ranked, 1):
        print(f"  {i}. {r['mmsi']} -- {r['vessel_name']}  "
              f"score={r['forward_score']:.3f}  "
              f"dist={r['distance_km']:.1f} km")

    print()
    print(f"Outcome: {outcome['outcome']}")
    print(f"Saved:   data/forward_attribution.json")
    from adapters.db_config import MOCK_MODE
    target = "mock DB" if MOCK_MODE else "PostgreSQL"
    print(f"Wrote {len(scores)} rows to drift_runs ({target})")
    print()
    print("Forward attribution complete.")
