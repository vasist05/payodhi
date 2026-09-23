import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from datetime import datetime
from core.phase3_drift.drift_model.runner import run_backward

scenario = {
    "detection_lon": 72.5,
    "detection_lat": 21.0,
    "detection_time": datetime(2024, 6, 15, 14, 0),
    "release_time": datetime(2024, 6, 15, 8, 0),
    "oil_type": "GENERIC HEAVY CRUDE",
}

if __name__ == "__main__":
    out = run_backward(
        scenario,
        wind="data/forcing/wind.nc",
        current="data/forcing/current.nc",
        wave="data/forcing/waves.nc",
    )
    print("Output:", out)
