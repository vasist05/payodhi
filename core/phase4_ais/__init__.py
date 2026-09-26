"""
Phase 4: AIS Pipeline & Dark Vessel Detection Package.
National Technical Research Organisation (NTRO) - SIH26143
"""

from .geo_utils import haversine, get_bounding_box, INDIAN_AOIS
from .cfar_detector import ca_cfar, detect_sar_ships, load_sar_scene
from .fetch_ais import fetch_live_ais, fetch_mock_ais, fetch_historical_ais
from .correlate import (
    correlate_sar_ais,
    compute_behavioral_anomaly,
    detect_ais_gaps,
    interpolate_position_at_time
)
from .geojson_exporter import save_geojson


def run_phase4_pipeline(*args, **kwargs):
    """Lazy loader for run_phase4_pipeline to avoid runpy package warnings."""
    from .pipeline import run_phase4_pipeline as _runner
    return _runner(*args, **kwargs)


__all__ = [
    "haversine",
    "get_bounding_box",
    "INDIAN_AOIS",
    "ca_cfar",
    "detect_sar_ships",
    "load_sar_scene",
    "fetch_live_ais",
    "fetch_mock_ais",
    "fetch_historical_ais",
    "correlate_sar_ais",
    "compute_behavioral_anomaly",
    "detect_ais_gaps",
    "interpolate_position_at_time",
    "save_geojson",
    "run_phase4_pipeline",
]
