"""
CA-CFAR (Cell Averaging Constant False Alarm Rate) Radar Target Detector.
Supports:
1. Real Sentinel-1 GeoTIFF (.tif) ingestion via rasterio with georeferenced pixel-to-coordinate transforms.
2. 2D CA-CFAR sliding-window detector (CUT, guard ring, training clutter cells).
3. Synthetic SAR scene simulation fallback for zero-dependency test suites and demos.
4. Morphological clustering / centroid calculation.
"""

from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import numpy as np


def ca_cfar(
    image: np.ndarray,
    guard_cells: int = 2,
    training_cells: int = 4,
    threshold_factor: float = 8.0
) -> np.ndarray:
    """
    2D Cell Averaging Constant False Alarm Rate (CA-CFAR) algorithm.

    Args:
        image: 2D numpy array representing SAR radar backscatter intensity.
        guard_cells: Guard window ring around CUT to prevent target energy leakage.
        training_cells: Outer ring estimating local sea clutter / wave noise.
        threshold_factor: Multiplier for adaptive thresholding over local background average.

    Returns:
        Boolean numpy array of detections matching input image shape.
    """
    if image.size == 0 or np.isnan(image).all():
        return np.zeros_like(image, dtype=bool)

    clean_img = np.nan_to_num(image, nan=0.0)
    rows, cols = clean_img.shape
    detections = np.zeros_like(clean_img, dtype=bool)
    pad = guard_cells + training_cells
    padded = np.pad(clean_img, pad, mode="constant", constant_values=float(np.median(clean_img)))

    for i in range(rows):
        for j in range(cols):
            window = padded[i : i + 2 * pad + 1, j : j + 2 * pad + 1]
            mask = np.ones(window.shape, dtype=bool)

            # Mask out CUT (Cell Under Test) and Guard Cells
            cut_r, cut_c = pad, pad
            g_start_r = cut_r - guard_cells
            g_end_r = cut_r + guard_cells + 1
            g_start_c = cut_c - guard_cells
            g_end_c = cut_c + guard_cells + 1
            mask[g_start_r:g_end_r, g_start_c:g_end_c] = False

            # Calculate local clutter noise level
            training_vals = window[mask]
            if len(training_vals) > 0:
                mean_clutter = np.mean(training_vals)
                adaptive_threshold = mean_clutter * threshold_factor
                cut_val = padded[i + pad, j + pad]
                if cut_val > adaptive_threshold:
                    detections[i, j] = True

    return detections


def cluster_detections(
    detections: np.ndarray,
    min_area: int = 1
) -> List[Tuple[float, float, int]]:
    """
    Groups contiguous detected pixels into clusters/connected components and finds centroid.
    Returns list of (row_centroid, col_centroid, area_pixels).
    Pure NumPy implementation without external dependencies.
    """
    if detections.size == 0 or not detections.any():
        return []

    rows, cols = detections.shape
    visited = np.zeros((rows, cols), dtype=bool)
    clusters = []

    for r in range(rows):
        for c in range(cols):
            if detections[r, c] and not visited[r, c]:
                # BFS connected component discovery
                component = []
                queue = [(r, c)]
                visited[r, c] = True
                while queue:
                    curr_r, curr_c = queue.pop(0)
                    component.append((curr_r, curr_c))
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = curr_r + dr, curr_c + dc
                            if 0 <= nr < rows and 0 <= nc < cols:
                                if detections[nr, nc] and not visited[nr, nc]:
                                    visited[nr, nc] = True
                                    queue.append((nr, nc))
                if len(component) >= min_area:
                    avg_r = sum(p[0] for p in component) / len(component)
                    avg_c = sum(p[1] for p in component) / len(component)
                    clusters.append((float(avg_r), float(avg_c), len(component)))

    return clusters


def load_sar_scene(
    sar_file_path: Optional[str] = None
) -> Tuple[Optional[np.ndarray], Optional[Any]]:
    """
    Loads a Sentinel-1 SAR raster image from a GeoTIFF (.tif) file.
    Returns:
        (sar_image_2d, affine_transform_or_none)
    """
    if not sar_file_path or not Path(sar_file_path).exists():
        return None, None

    try:
        import rasterio
        with rasterio.open(sar_file_path) as src:
            band = src.read(1).astype(np.float32)
            band = np.nan_to_num(band, nan=0.0)
            b_min, b_max = np.percentile(band, 1), np.percentile(band, 99)
            if b_max > b_min:
                normalized = np.clip((band - b_min) / (b_max - b_min), 0.0, 1.0)
            else:
                normalized = np.zeros_like(band)
            print(f"   [SAR LOAD] Loaded GeoTIFF: {sar_file_path} ({band.shape[0]}x{band.shape[1]} px, CRS: {src.crs})")
            return normalized, src.transform
    except ImportError:
        print("   [SAR LOAD WARNING] rasterio is not installed. To load real GeoTIFFs, run `pip install rasterio`.")
    except Exception as e:
        print(f"   [SAR LOAD WARNING] Could not read GeoTIFF {sar_file_path}: {e}")

    return None, None


def detect_sar_ships(
    sar_file: Optional[str] = None,
    sar_image_path: Optional[str] = None,
    spill_lat: float = 18.90,
    spill_lon: float = 72.10,
    ais_ships: Optional[List[Dict]] = None,
    ais_targets: Optional[List[Dict]] = None,
    sar_image: Optional[np.ndarray] = None,
    grid_size: int = 100,
    span_deg: float = 0.5,
    inject_dark: bool = True,
    dark_offset_lat: float = 0.12,
    dark_offset_lon: float = 0.14
) -> List[Dict]:
    """
    Identifies vessel targets in a SAR image using CA-CFAR.
    Supports real Sentinel-1 GeoTIFF rasters via `sar_file`,
    with seamless fallback to synthetic radar simulation.
    """
    actual_file = sar_file or sar_image_path
    actual_ais = ais_ships if ais_ships is not None else (ais_targets if ais_targets is not None else [])

    transform = None

    # Attempt to load real GeoTIFF if path provided
    if actual_file:
        loaded_img, transform = load_sar_scene(actual_file)
        if loaded_img is not None:
            sar_image = loaded_img

    if sar_image is None:
        # Generate calibrated sea clutter simulation
        np.random.seed(42)
        sar_image = np.random.normal(loc=0.05, scale=0.008, size=(grid_size, grid_size))
        sar_image = np.clip(sar_image, 0.0, 1.0)

        def latlon_to_pixel(lat: float, lon: float) -> Tuple[int, int]:
            row = int(((lat - spill_lat) / span_deg + 0.5) * grid_size)
            col = int(((lon - spill_lon) / span_deg + 0.5) * grid_size)
            row = max(0, min(grid_size - 1, row))
            col = max(0, min(grid_size - 1, col))
            return row, col

        # Inject bright radar returns at every AIS ship coordinate
        for ship in actual_ais:
            if "lat" in ship and "lon" in ship:
                r, c = latlon_to_pixel(ship["lat"], ship["lon"])
                sar_image[r, c] = 0.90

        # Inject dark vessel contact (no AIS broadcast)
        if inject_dark:
            dark_lat = spill_lat + dark_offset_lat
            dark_lon = spill_lon + dark_offset_lon
            dr, dc = latlon_to_pixel(dark_lat, dark_lon)
            sar_image[dr, dc] = 0.95
            print(f"   [SAR INJECT] Dark vessel contact injected at ({dark_lat:.4f} N, {dark_lon:.4f} E)")

    # Run CA-CFAR detector
    detections = ca_cfar(
        sar_image,
        guard_cells=2,
        training_cells=4,
        threshold_factor=8.0
    )
    ship_pixels = np.argwhere(detections)

    sar_ships = []
    for idx, (row, col) in enumerate(ship_pixels, start=1):
        if transform is not None:
            lon_x, lat_y = transform * (col, row)
            lat = float(lat_y)
            lon = float(lon_x)
        else:
            lat = spill_lat + ((row / grid_size) - 0.5) * span_deg
            lon = spill_lon + ((col / grid_size) - 0.5) * span_deg

        intensity = float(sar_image[row, col])
        estimated_length = round(40.0 + (intensity * 260.0), 1)

        sar_ships.append({
            "sar_id": idx,
            "target_id": f"SAR-{idx:03d}",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "pixel_row": int(row),
            "pixel_col": int(col),
            "intensity": round(intensity, 3),
            "estimated_length_m": estimated_length,
            "confidence": round(min(0.99, 0.65 + (intensity * 0.3)), 2)
        })

    print(f"   [SAR DETECT] Identified {len(sar_ships)} high-confidence radar vessel contacts via CA-CFAR.")
    return sar_ships
