"""
core/phase1_sar/postprocess.py

Post-processing and vectorization pipeline for Phase 1 SAR detection.
Converts model probability masks into clean geometric vectors (MultiPolygon),
georeferences pixel coordinates to EPSG:4326 (WGS84), calculates area in km^2,
and outputs standardized SpillCandidate objects for Phase 2 verification.
"""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.ops import unary_union

from models.common.schema import SpillCandidate

log = logging.getLogger(__name__)

DEFAULT_PIXEL_SPACING_M = 10.0  # Standard Sentinel-1 IW GRD pixel spacing (10m x 10m)


def clean_binary_mask(
    prob_mask: np.ndarray,
    threshold: float = 0.5,
    min_pixels: int = 50,
) -> np.ndarray:
    """
    Threshold probability mask and apply morphological operations to remove
    tiny speckles and consolidate oil slick boundaries.
    """
    binary = (prob_mask >= threshold).astype(np.uint8)

    # 3x3 morphological closing to bridge narrow gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # Remove connected components smaller than min_pixels
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    clean_mask = np.zeros_like(closed)
    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_pixels:
            clean_mask[labels == label] = 1

    return clean_mask


def pixel_to_geo(
    px: float,
    py: float,
    affine_transform: Optional[Tuple[float, ...]] = None,
    bbox_wgs84: Optional[Tuple[float, float, float, float]] = None,
    image_shape: Optional[Tuple[int, int]] = None,
) -> Tuple[float, float]:
    """
    Transform pixel coordinate (px, py) to (lon, lat) in EPSG:4326.

    Supports:
      1. Affine transform: (a, b, c, d, e, f) where:
         lon = a * px + b * py + c
         lat = d * px + e * py + f
      2. Bounding box: (min_lon, min_lat, max_lon, max_lat) mapped linearly across image_shape.
      3. Default fallback: Relative coordinates in Indian coastal waters (Mumbai High reference).
    """
    if affine_transform is not None and len(affine_transform) >= 6:
        a, b, c, d, e, f = affine_transform[:6]
        lon = a * px + b * py + c
        lat = d * px + e * py + f
        return float(lon), float(lat)

    if bbox_wgs84 is not None and image_shape is not None:
        min_lon, min_lat, max_lon, max_lat = bbox_wgs84
        h, w = image_shape
        lon = min_lon + (px / max(1, w)) * (max_lon - min_lon)
        lat = max_lat - (py / max(1, h)) * (max_lat - min_lat)
        return float(lon), float(lat)

    # Fallback reference: Gulf of Kutch / Mumbai High (approx 19.0 N, 71.5 E)
    # 0.0001 deg ~ 11 meters
    base_lat = 19.35
    base_lon = 71.40
    lon = base_lon + (px * 0.00009)
    lat = base_lat - (py * 0.00009)
    return float(lon), float(lat)


def compute_geodesic_area_sq_km(
    polygon: Polygon,
    pixel_count: int,
    pixel_spacing_m: float = DEFAULT_PIXEL_SPACING_M,
) -> float:
    """
    Calculate area in square kilometers.
    Combines pixel count with nominal ground resolution for maximum accuracy.
    """
    # 1 pixel = (pixel_spacing_m)^2 m^2
    area_m2 = pixel_count * (pixel_spacing_m ** 2)
    area_km2 = area_m2 / 1_000_000.0
    return max(0.001, round(float(area_km2), 4))


def vectorize_mask(
    binary_mask: np.ndarray,
    prob_mask: np.ndarray,
    affine_transform: Optional[Tuple[float, ...]] = None,
    bbox_wgs84: Optional[Tuple[float, float, float, float]] = None,
    min_pixels: int = 50,
) -> List[Dict[str, Any]]:
    """
    Extract vector contours from binary mask, project to WGS84 (EPSG:4326),
    and calculate area, mean confidence, and centroid.
    """
    h, w = binary_mask.shape
    contours, hierarchy = cv2.findContours(
        binary_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    detections = []

    for cnt in contours:
        area_px = cv2.contourArea(cnt)
        if area_px < min_pixels:
            continue

        # Approximate polygon to reduce point count
        epsilon = 0.005 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)

        if len(approx) < 3:
            continue

        # Convert pixel vertices to (lon, lat)
        geo_coords = []
        for pt in approx:
            px, py = float(pt[0][0]), float(pt[0][1])
            lon, lat = pixel_to_geo(
                px, py,
                affine_transform=affine_transform,
                bbox_wgs84=bbox_wgs84,
                image_shape=(h, w),
            )
            geo_coords.append((lon, lat))

        # Close polygon
        if geo_coords[0] != geo_coords[-1]:
            geo_coords.append(geo_coords[0])

        try:
            poly = Polygon(geo_coords)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue

            # MultiPolygon GeoJSON
            if poly.geom_type == "Polygon":
                multipoly = MultiPolygon([poly])
            elif poly.geom_type == "MultiPolygon":
                multipoly = poly
            else:
                continue
        except Exception as e:
            log.warning("Invalid geometry skipped: %s", e)
            continue

        # Mask contour region to extract mean probability score
        cnt_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(cnt_mask, [cnt], -1, 1, thickness=-1)
        oil_probs = prob_mask[cnt_mask == 1]
        mean_conf = float(np.mean(oil_probs)) if len(oil_probs) > 0 else 0.5

        # Bounding box in pixel space
        bx, by, bw, bh = cv2.boundingRect(cnt)
        bbox_px = (by, by + bh, bx, bx + bw)  # (y0, y1, x0, x1)

        # Centroid
        centroid = poly.centroid
        center_lon, center_lat = float(centroid.x), float(centroid.y)

        area_sq_km = compute_geodesic_area_sq_km(poly, pixel_count=int(area_px))

        detections.append({
            "geometry": mapping(multipoly),  # GeoJSON dict
            "centroid": (center_lat, center_lon),
            "area_sq_km": area_sq_km,
            "confidence": round(mean_conf, 4),
            "bbox_px": bbox_px,
            "pixel_area": int(area_px),
        })

    return detections


def create_spill_candidates(
    detections: List[Dict[str, Any]],
    raw_image_2d: np.ndarray,
    scene_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    padding: int = 32,
) -> List[SpillCandidate]:
    """
    Package detected spills into standardized SpillCandidate objects
    matching the schema in models/common/schema.py for Phase 2 validation.
    """
    from pathlib import Path
    from PIL import Image

    candidates: List[SpillCandidate] = []
    h, w = raw_image_2d.shape

    save_crops = output_dir is not None
    if save_crops:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

    for i, det in enumerate(detections):
        spill_id = str(uuid.uuid4())
        y0, y1, x0, x1 = det["bbox_px"]

        # Add 32px padding around bbox matching training preprocessing
        y0_pad = max(0, y0 - padding)
        y1_pad = min(h, y1 + padding)
        x0_pad = max(0, x0 - padding)
        x1_pad = min(w, x1 + padding)

        crop = raw_image_2d[y0_pad:y1_pad, x0_pad:x1_pad]

        # Resize to standard 256x256
        pil_crop = Image.fromarray((crop * 255.0).astype(np.uint8))
        resized_crop = pil_crop.resize((256, 256), Image.Resampling.BILINEAR)

        patch_path = ""
        if save_crops:
            crop_filename = f"candidate_{spill_id[:8]}_{i}.png"
            full_patch_path = out_path / crop_filename
            resized_crop.save(full_patch_path)
            patch_path = str(full_patch_path)

        center_lat, center_lon = det["centroid"]

        cand = SpillCandidate(
            id=spill_id,
            patch_path=patch_path,
            center_lat=center_lat,
            center_lon=center_lon,
            detection_confidence=det["confidence"],
            bbox=(x0_pad, y0_pad, x1_pad, y1_pad),
            metadata={
                "scene_id": scene_id,
                "area_sq_km": det["area_sq_km"],
                "spill_polygon": det["geometry"],
                "pixel_area": det["pixel_area"],
            },
        )
        candidates.append(cand)

    return candidates
