import numpy as np
from datetime import timedelta

OIL_TYPES = [
    "GENERIC HEAVY CRUDE",
    "GENERIC MEDIUM CRUDE",
    "GENERIC LIGHT CRUDE",
    "ARABIAN HEAVY",
    "ARABIAN LIGHT",
    "DIESEL",
    "FUEL OIL NO. 6",
    "IFO 180",
    "IFO 380",
    "GASOLINE",
]


def sample_scenarios(det_lon, det_lat, det_time,
                     window_hours=12, n=100, seed=42):
    """Generate N perturbed scenarios. Each samples release time + oil type."""
    rng = np.random.default_rng(seed)
    window_start = det_time - timedelta(hours=window_hours)
    out = []
    for _ in range(n):
        frac = rng.random()
        release = window_start + frac * (det_time - window_start)
        oil = OIL_TYPES[rng.integers(0, len(OIL_TYPES))]
        out.append({
            "detection_lon": det_lon,
            "detection_lat": det_lat,
            "detection_time": det_time,
            "release_time": release,
            "oil_type": oil,
        })
    return out