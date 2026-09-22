"""
scripts/join_era5_metadata.py

Bilinear-joins ERA5 U10/V10 from cached NetCDF into wind_metadata.json.
Idempotent: re-running skips patches that already have u10/v10
unless --overwrite is passed.
"""
import argparse
import json
from pathlib import Path

import xarray as xr


def find_nc(cache_dir: Path, region: str, date: str) -> Path:
    p = cache_dir / f"{region}_{date}.nc"
    if not p.exists():
        raise FileNotFoundError(f"Missing ERA5 file: {p}")
    return p


def nearest_u_v(ds: xr.Dataset, lat: float, lon: float, iso_time: str):
    lon_query = lon
    if ds.longitude.min() >= 0 and lon < 0:
        lon_query = lon % 360
    t = iso_time.rstrip("Z")
    time_coord = "valid_time" if "valid_time" in ds.coords else "time"
    sel_kwargs = {"latitude": lat, "longitude": lon_query, time_coord: t}
    u = ds["u10"].sel(method="nearest", **sel_kwargs).values.item()
    v = ds["v10"].sel(method="nearest", **sel_kwargs).values.item()
    return float(u), float(v)


def main(metadata_file: str, cache_dir: str, overwrite: bool = False):
    meta_path = Path(metadata_file)
    cache = Path(cache_dir)
    with open(meta_path) as f:
        meta = json.load(f)

    opened_datasets = {}
    def get_dataset(nc_path: Path) -> xr.Dataset:
        if nc_path not in opened_datasets:
            opened_datasets[nc_path] = xr.open_dataset(nc_path)
        return opened_datasets[nc_path]

    joined, skipped, missing = 0, 0, 0
    try:
        for fname, rec in meta.items():
            if (not overwrite
                    and rec.get("u10") is not None
                    and rec.get("v10") is not None
                    and rec.get("wind_source") != "Regional Physics"):
                skipped += 1
                continue
            try:
                nc = find_nc(cache, rec["region_tag"], rec["timestamp"][:10])
                ds = get_dataset(nc)
                u, v = nearest_u_v(ds, rec["lat"], rec["lon"], rec["timestamp"])
                rec["u10"] = u
                rec["v10"] = v
                # Strip legacy synthetic fields
                rec.pop("wind_source", None)
                rec.pop("wind_speed", None)
                rec.pop("wind_direction", None)
                joined += 1
            except Exception as e:
                missing += 1
                rec["u10"] = None
                rec["v10"] = None
    finally:
        for ds in opened_datasets.values():
            ds.close()

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Joined: {joined}  Skipped: {skipped}  Missing: {missing}")
    if missing:
        print(f"WARNING: {missing} patches lack ERA5.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--metadata", default="data/fp_filter/wind_metadata.json")
    p.add_argument("--cache-dir", dest="cache_dir", default="data/fp_filter/era5_cache")
    p.add_argument("--overwrite", action="store_true",
                   help="Overwrite existing wind values (recommended)")
    args = p.parse_args()
    main(args.metadata, args.cache_dir, args.overwrite)
