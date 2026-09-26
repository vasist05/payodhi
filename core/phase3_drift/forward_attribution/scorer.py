import os
import numpy as np
import xarray as xr


def _haversine_km(lon1, lat1, lon2, lat2):
    """Great-circle distance in km."""
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
         np.sin(dlon / 2) ** 2)
    return float(2 * R * np.arcsin(np.sqrt(a)))


def _forward_centroid(nc_file):
    """Centroid of forward-simulation particles at final timestep."""
    ds = xr.open_dataset(nc_file)
    lon = ds["lon"].values[:, -1]
    lat = ds["lat"].values[:, -1]
    m = np.isfinite(lon) & np.isfinite(lat)
    if m.sum() == 0:
        ds.close()
        return (np.nan, np.nan)
    c = (float(np.mean(lon[m])), float(np.mean(lat[m])))
    ds.close()
    return c


def score_vessel(candidate, detection_lon, detection_lat,
                 wind, current, wave=None,
                 outdir="data/forward_outputs",
                 stokes="wave", threshold_km=30.0):
    """
    Run forward simulation from candidate vessel's position at release time.
    Score = how close predicted slick centroid lands to actual detection.

    candidate = {
        "mmsi": str,
        "lon": float, "lat": float,
        "release_time": datetime,
        "detection_time": datetime,
        "oil_type": str,
    }
    """
    from core.phase3_drift.drift_model.runner import run_forward

    os.makedirs(outdir, exist_ok=True)
    outfile = os.path.join(outdir, f"fwd_{candidate['mmsi']}.nc")

    try:
        run_forward(
            lon=candidate["lon"],
            lat=candidate["lat"],
            release_time=candidate["release_time"],
            end_time=candidate["detection_time"],
            oil_type=candidate["oil_type"],
            wind=wind, current=current, wave=wave,
            outfile=outfile, stokes=stokes,
        )
    except Exception as e:
        return {
            "mmsi": candidate["mmsi"],
            "vessel_name": candidate.get("vessel_name", ""),
            "forward_score": 0.0,
            "distance_km": None,
            "predicted_centroid": None,
            "error": str(e),
        }

    centroid = _forward_centroid(outfile)
    if np.isnan(centroid[0]):
        return {
            "mmsi": candidate["mmsi"],
            "vessel_name": candidate.get("vessel_name", ""),
            "forward_score": 0.0,
            "distance_km": None,
            "predicted_centroid": None,
            "error": "no valid particles at final step",
        }

    dist = _haversine_km(centroid[0], centroid[1],
                        detection_lon, detection_lat)
    score = max(0.0, 1.0 - dist / threshold_km)

    return {
        "mmsi": candidate["mmsi"],
        "vessel_name": candidate.get("vessel_name", ""),
        "forward_score": score,
        "distance_km": dist,
        "predicted_centroid": centroid,
        "release_time": str(candidate["release_time"]),
        "oil_type": candidate["oil_type"],
    }