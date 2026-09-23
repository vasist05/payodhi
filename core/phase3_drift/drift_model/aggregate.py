import numpy as np
import xarray as xr


def build_heatmap(nc_files, lon_bounds, lat_bounds, resolution=0.02):
    """Bin all particle positions from all runs into a 2D probability grid."""
    lon_bins = np.arange(lon_bounds[0], lon_bounds[1], resolution)
    lat_bins = np.arange(lat_bounds[0], lat_bounds[1], resolution)
    H = np.zeros((len(lat_bins) - 1, len(lon_bins) - 1))

    for f in nc_files:
        ds = xr.open_dataset(f)
        lon = ds["lon"].values[:, -1]
        lat = ds["lat"].values[:, -1]
        m = np.isfinite(lon) & np.isfinite(lat)
        if m.sum() == 0:
            ds.close()
            continue
        h, _, _ = np.histogram2d(lat[m], lon[m], bins=[lat_bins, lon_bins])
        H += h
        ds.close()

    if H.sum() > 0:
        H /= H.sum()
    return H, lon_bins, lat_bins


def confidence_contours(H, levels=(0.5, 0.75, 0.9)):
    """Return boolean masks for cumulative probability contours."""
    flat = H.ravel()
    order = np.argsort(flat)[::-1]
    cum = np.cumsum(flat[order])
    out = {}
    for lvl in levels:
        cut = np.searchsorted(cum, lvl)
        m = np.zeros_like(flat, dtype=bool)
        m[order[:cut + 1]] = True
        out[lvl] = m.reshape(H.shape)
    return out


def peak_location(H, lon_bins, lat_bins):
    """Return the highest-probability cell center."""
    iy, ix = np.unravel_index(H.argmax(), H.shape)
    return {
        "lon": float((lon_bins[ix] + lon_bins[ix + 1]) / 2),
        "lat": float((lat_bins[iy] + lat_bins[iy + 1]) / 2),
        "prob": float(H[iy, ix]),
    }


def contour_to_polygon(mask, lon_bins, lat_bins):
    """Bounding box of a contour mask (simple version)."""
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return []
    return [[
        [float(lon_bins[xs.min()]), float(lat_bins[ys.min()])],
        [float(lon_bins[xs.max()]), float(lat_bins[ys.min()])],
        [float(lon_bins[xs.max()]), float(lat_bins[ys.max()])],
        [float(lon_bins[xs.min()]), float(lat_bins[ys.max()])],
        [float(lon_bins[xs.min()]), float(lat_bins[ys.min()])],
    ]]