from concurrent.futures import ThreadPoolExecutor
from functools import partial
from .runner import run_backward
from .aggregate import build_heatmap, confidence_contours, peak_location


def _run_one(scenario, wind, current, wave, outdir, stokes):
    try:
        return run_backward(scenario, wind, current, wave,
                            outdir=outdir, stokes=stokes)
    except Exception as e:
        print(f"FAILED release={scenario.get('release_time')}: {e}")
        return None


def run_backward_ensemble(scenarios, wind, current, wave,
                          outdir="data/ensemble_outputs",
                          stokes="wave", n_workers=4):
    """Run N backward simulations in parallel via ThreadPoolExecutor (safe across Linux/Windows/macOS)."""
    fn = partial(_run_one, wind=wind, current=current, wave=wave,
                 outdir=outdir, stokes=stokes)
    if n_workers <= 1 or len(scenarios) <= 1:
        files = [fn(s) for s in scenarios]
    else:
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            files = list(executor.map(fn, scenarios))
    files = [f for f in files if f is not None]
    print(f"Completed {len(files)}/{len(scenarios)} backward runs")
    return files


def full_backward_pipeline(scenarios, wind, current, wave,
                           lon_bounds, lat_bounds,
                           outdir="data/ensemble_outputs",
                           stokes="wave", n_workers=4):
    """Backward ensemble -> heatmap + contours + peak."""
    files = run_backward_ensemble(scenarios, wind, current, wave,
                                  outdir=outdir, stokes=stokes,
                                  n_workers=n_workers)
    if not files:
        raise RuntimeError("All backward runs failed")

    H, lon_bins, lat_bins = build_heatmap(files, lon_bounds, lat_bounds)
    contours = confidence_contours(H)
    peak = peak_location(H, lon_bins, lat_bins)

    return {
        "files": files,
        "grid": H,
        "lon_bins": lon_bins,
        "lat_bins": lat_bins,
        "contours": contours,
        "peak": peak,
    }