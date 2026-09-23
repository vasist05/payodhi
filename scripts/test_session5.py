import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from datetime import datetime


if __name__ == "__main__":
    from core.phase3_drift.drift_model.sampler import sample_scenarios
    from core.phase3_drift.drift_model.orchestrate import full_backward_pipeline

    scenarios = sample_scenarios(
        72.5, 21.0, datetime(2024, 6, 15, 14, 0),
        window_hours=12, n=5,
    )

    print(f"Running {len(scenarios)} scenarios...")

    result = full_backward_pipeline(
        scenarios,
        wind="data/forcing/wind.nc",
        current="data/forcing/current.nc",
        wave="data/forcing/waves.nc",
        lon_bounds=(71.5, 73.5),
        lat_bounds=(20.5, 21.5),
        n_workers=4,
    )

    print(f"\nPeak origin: ({result['peak']['lon']:.3f}, "
          f"{result['peak']['lat']:.3f})")
    print(f"Grid shape: {result['grid'].shape}")
    print(f"Files produced: {len(result['files'])}")
    print()
    print("Session 5 OK")
