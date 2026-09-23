"""Return paths to local NetCDF forcing files.

Note: the DB environmental_data table stores point values (source/variable/
valid_time/location/value), not file paths. Phase 3 uses local NetCDF files
instead. If real files aren't present, fall back to synthetic.
"""
import os


def read_environmental(scene_id: str = None):
    wind = "data/forcing/wind.nc"
    current = "data/forcing/current.nc"
    wave = "data/forcing/waves.nc"

    if not os.path.exists(wind):
        wind = "data/forcing/wind_synthetic.nc"
    if not os.path.exists(current):
        current = "data/forcing/current_synthetic.nc"
    if not os.path.exists(wave):
        wave = None

    return {
        "wind_file": wind,
        "current_file": current,
        "wave_file": wave,
    }