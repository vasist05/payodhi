import os


def _naive(dt):
    """Convert timezone-aware datetime to naive UTC for OpenDrift."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _configure_stokes(o, mode):
    if mode == "tabular":
        o.set_config('drift:use_tabularised_stokes_drift', True)
    elif mode == "windage":
        o.set_config('drift:wind_drift_factor', 0.035)


def run_backward(scenario, wind, current, wave=None,
                 outdir="data/ensemble_outputs", n=500, stokes="wave"):
    """Backward drift: detection -> origin. Weathering is auto-skipped."""
    from opendrift.models.openoil import OpenOil
    from .forcing import load_forcing, load_forcing_safe

    wind, current, wave = load_forcing_safe(wind, current, wave)

    os.makedirs(outdir, exist_ok=True)
    o = OpenOil(loglevel=20)
    for r in load_forcing(wind, current, wave):
        o.add_reader(r)
    _configure_stokes(o, stokes)

    det_t = _naive(scenario["detection_time"])
    rel_t = _naive(scenario["release_time"])

    o.seed_elements(
        lon=scenario["detection_lon"],
        lat=scenario["detection_lat"],
        radius=1000,
        number=n,
        time=det_t,
        oil_type=scenario["oil_type"],
    )

    outfile = os.path.join(
        outdir,
        f"bwd_{rel_t:%Y%m%dT%H%M}_"
        f"{scenario['oil_type'].replace(' ', '_')[:12]}.nc"
    )

    o.run(
        end_time=rel_t,
        time_step=-900,
        time_step_output=1800,
        outfile=outfile,
    )
    return outfile


def run_forward(lon, lat, release_time, end_time, oil_type,
                wind, current, wave=None,
                outfile="data/forward_outputs/fwd.nc",
                n=500, stokes="wave"):
    """Forward drift: vessel -> predicted slick. Weathering evolves."""
    from opendrift.models.openoil import OpenOil
    from .forcing import load_forcing, load_forcing_safe

    wind, current, wave = load_forcing_safe(wind, current, wave)

    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    o = OpenOil(loglevel=20)
    for r in load_forcing(wind, current, wave):
        o.add_reader(r)
    _configure_stokes(o, stokes)

    rel_t = _naive(release_time)
    end_t = _naive(end_time)

    o.seed_elements(
        lon=lon, lat=lat, radius=1000,
        number=n, time=rel_t, oil_type=oil_type,
    )

    o.run(
        end_time=end_t,
        time_step=900,
        time_step_output=1800,
        outfile=outfile,
    )
    return outfile