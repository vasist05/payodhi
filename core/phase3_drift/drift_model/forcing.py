import os
import numpy as np
import xarray as xr
def load_forcing(wind, current, wave=None):
    """Return list of OpenOil readers."""
    from opendrift.readers import reader_netCDF_CF_generic
    readers = [
        reader_netCDF_CF_generic.Reader(wind),
        reader_netCDF_CF_generic.Reader(current),
    ]
    if wave:
        readers.append(reader_netCDF_CF_generic.Reader(wave))
    return readers


def make_synthetic_wind(path="data/forcing/wind_synthetic.nc"):
    """Fallback: constant 5 m/s eastward wind with CF standard_names.
    Grid: 18-24 N, 69-76 E. Time: 2024-06-14 to 2024-06-16."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    times = np.array([
        "2024-06-14T00", "2024-06-15T00",
        "2024-06-15T12", "2024-06-16T00",
    ], dtype="datetime64[ns]")
    lats = np.linspace(18, 24, 30)
    lons = np.linspace(69, 76, 30)

    ds = xr.Dataset(
        {
            "x_wind": (("time", "lat", "lon"),
                       np.full((4, 30, 30), 5.0),
                       {"standard_name": "eastward_wind",
                        "units": "m/s",
                        "long_name": "Eastward wind"}),
            "y_wind": (("time", "lat", "lon"),
                       np.zeros((4, 30, 30)),
                       {"standard_name": "northward_wind",
                        "units": "m/s",
                        "long_name": "Northward wind"}),
        },
        coords={
            "time": ("time", times, {"standard_name": "time"}),
            "lat":  ("lat",  lats,  {"standard_name": "latitude",
                                     "units": "degrees_north"}),
            "lon":  ("lon",  lons,  {"standard_name": "longitude",
                                     "units": "degrees_east"}),
        },
        attrs={"Conventions": "CF-1.6"},
    )
    ds.to_netcdf(path)
    return path


def make_synthetic_current(path="data/forcing/current_synthetic.nc"):
    """Fallback: constant 0.2 m/s eastward current with CF standard_names.
    Grid: 18-24 N, 69-76 E. Time: 2024-06-14 to 2024-06-16."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    times = np.array([
        "2024-06-14T00", "2024-06-15T00",
        "2024-06-15T12", "2024-06-16T00",
    ], dtype="datetime64[ns]")
    lats = np.linspace(18, 24, 30)
    lons = np.linspace(69, 76, 30)

    ds = xr.Dataset(
        {
            "x_sea_water_velocity": (("time", "lat", "lon"),
                                     np.full((4, 30, 30), 0.2),
                                     {"standard_name": "eastward_sea_water_velocity",
                                      "units": "m/s",
                                      "long_name": "Eastward current"}),
            "y_sea_water_velocity": (("time", "lat", "lon"),
                                     np.zeros((4, 30, 30)),
                                     {"standard_name": "northward_sea_water_velocity",
                                      "units": "m/s",
                                      "long_name": "Northward current"}),
        },
        coords={
            "time": ("time", times, {"standard_name": "time"}),
            "lat":  ("lat",  lats,  {"standard_name": "latitude",
                                     "units": "degrees_north"}),
            "lon":  ("lon",  lons,  {"standard_name": "longitude",
                                     "units": "degrees_east"}),
        },
        attrs={"Conventions": "CF-1.6"},
    )
    ds.to_netcdf(path)
    return path


def load_forcing_safe(wind, current, wave=None):
    """Check files exist, fall back to synthetic if missing.
    Uses absolute paths so working-directory changes don't confuse checks."""
    wind_abs = os.path.abspath(wind)
    current_abs = os.path.abspath(current)

    if not os.path.exists(wind_abs):
        print(f"WARNING: {wind} missing -> using synthetic wind")
        wind = make_synthetic_wind()
    else:
        wind = wind_abs

    if not os.path.exists(current_abs):
        print(f"WARNING: {current} missing -> using synthetic current")
        current = make_synthetic_current()
    else:
        current = current_abs

    if wave:
        wave_abs = os.path.abspath(wave)
        if not os.path.exists(wave_abs):
            print(f"WARNING: {wave} missing -> disabling wave/Stokes")
            wave = None
        else:
            wave = wave_abs

    return wind, current, wave