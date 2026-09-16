"""
Integrated Oil Spill Pipeline: Phase 1 (Detection) -> Phase 2 (SAR-UV Filtering) -> Phase 3 (Drift Polygon Export).
Executes segmentation, validates candidates with directional wind channels, and outputs verified polygons for drift simulation.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from models.common.schema import SpillCandidate, SpillPolygon
from models.detection.inference import detect_spills
from models.false_positive_filter.inference import SpillFilter


class IntegratedSpillPipeline:
    """
    End-to-End Orchestrator chaining Phase 1 Detection and Phase 2 False-Positive Filtering.
    """

    def __init__(
        self,
        fp_filter_mode: str = "sar_uv",
        polygons_dir: str = "data/processed/polygons",
        rejected_dir: str = "data/processed/rejected_lookalikes",
        filter_threshold: float = 0.5,
    ):
        self.polygons_dir = Path(polygons_dir)
        self.rejected_dir = Path(rejected_dir)
        self.filter_threshold = filter_threshold

        self.polygons_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_dir.mkdir(parents=True, exist_ok=True)

        print(f"[Pipeline] Initializing Phase 2 SpillFilter (mode: {fp_filter_mode})...")
        self.spill_filter = SpillFilter(mode=fp_filter_mode)

    def process_scene(
        self,
        scene_path: str,
        scene_meta: Optional[dict] = None,
        wind_uv: Optional[Tuple[float, float]] = None,
    ) -> Dict[str, Any]:
        """
        Runs the full Phase 1 -> Phase 2 detection & filtering pipeline on a SAR scene.
        
        Args:
            scene_path: Path to SAR image file
            scene_meta: Geographic and temporal metadata
            wind_uv: Optional (U10, V10) wind vector override in m/s
        
        Returns:
            Dictionary containing confirmed polygons, rejected lookalikes, export paths, and summary stats.
        """
        if scene_meta is None:
            scene_meta = {}

        scene_name = Path(scene_path).stem
        print("\n" + "=" * 70)
        print(f"[Pipeline] RUNNING INTEGRATED SPILL DETECTION ON: {Path(scene_path).name}")
        print("=" * 70)

        # -------------------------------------------------------------
        # STEP 1: Phase 1 SAR Segmentation (Candidate Proposal)
        # -------------------------------------------------------------
        print("\n[Stage 1/2] Phase 1 SAR U-Net Segmentation...")
        candidates: List[SpillCandidate] = detect_spills(scene_path=scene_path, scene_meta=scene_meta)
        print(f" -> Phase 1 proposed {len(candidates)} candidate spill regions.")

        if not candidates:
            print(" -> No spill candidates detected in scene.")
            return {
                "status": "NO_DETECTIONS",
                "scene_id": scene_meta.get("scene_id", scene_name),
                "total_candidates": 0,
                "confirmed_spills": [],
                "rejected_lookalikes": [],
                "polygon_json_path": None,
            }

        # -------------------------------------------------------------
        # STEP 2: Phase 2 SAR-UV False-Positive Filtering
        # -------------------------------------------------------------
        print("\n[Stage 2/2] Phase 2 SAR-UV Wind-Integrated Lookalike Filtering...")
        wind_dict = {}
        if wind_uv is not None:
            for c in candidates:
                wind_dict[c.id] = wind_uv

        confirmed_candidates, rejected_candidates = self.spill_filter.filter_candidates(
            candidates=candidates,
            wind_dict=wind_dict if wind_dict else None,
            threshold=self.filter_threshold,
        )

        print(f" -> Confirmed Oil Spills    : {len(confirmed_candidates)}")
        print(f" -> Rejected Lookalikes (FP): {len(rejected_candidates)}")

        # -------------------------------------------------------------
        # STEP 3: Convert Confirmed Candidates to SpillPolygon (for Phase 3)
        # -------------------------------------------------------------
        scene_id = scene_meta.get("scene_id", scene_name)
        timestamp = scene_meta.get("acquisition_time", datetime.now())
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except Exception:
                timestamp = datetime.now()

        confirmed_polygons: List[SpillPolygon] = []
        for c in confirmed_candidates:
            # Construct polygon points from contour or geo-bbox
            if c.contour_points and len(c.contour_points) >= 3:
                poly_pts = c.contour_points
            else:
                d_lat, d_lon = 0.003, 0.003
                poly_pts = [
                    (c.center_lat - d_lat, c.center_lon - d_lon),
                    (c.center_lat - d_lat, c.center_lon + d_lon),
                    (c.center_lat + d_lat, c.center_lon + d_lon),
                    (c.center_lat + d_lat, c.center_lon - d_lon),
                    (c.center_lat - d_lat, c.center_lon - d_lon),
                ]

            poly = SpillPolygon(
                id=c.id,
                scene_id=scene_id,
                timestamp=c.timestamp or timestamp,
                centroid=(c.center_lat, c.center_lon),
                confidence=round((c.detection_confidence + (c.filter_confidence or 0.9)) / 2.0, 4),
                is_verified_oil=True,
                filter_confidence=c.filter_confidence,
                wind_u10=c.wind_u10,
                wind_v10=c.wind_v10,
                polygon=poly_pts,
            )
            confirmed_polygons.append(poly)

        # -------------------------------------------------------------
        # STEP 4: Export Deliverables
        # -------------------------------------------------------------
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S") if isinstance(timestamp, datetime) else "latest"
        polygon_json_path = self.polygons_dir / f"spill_polygons_{scene_id}_{ts_str}.json"

        # Save Phase 3 Drift input JSON
        polygon_dicts = [p.to_json() for p in confirmed_polygons]
        with open(polygon_json_path, "w", encoding="utf-8") as f:
            json.dump(polygon_dicts, f, indent=2)

        # Save Phase 2 Rejection telemetry
        rejected_json_path = self.rejected_dir / f"rejected_lookalikes_{scene_id}_{ts_str}.json"
        rejected_data = [
            {
                "id": r.id,
                "center_lat": r.center_lat,
                "center_lon": r.center_lon,
                "detection_confidence": r.detection_confidence,
                "filter_confidence": r.filter_confidence,
                "patch_path": r.patch_path,
                "wind_u10": r.wind_u10,
                "wind_v10": r.wind_v10,
                "rejection_reason": "Low oil likelihood / ocean lookalike signature under wind context",
            }
            for r in rejected_candidates
        ]
        with open(rejected_json_path, "w", encoding="utf-8") as f:
            json.dump(rejected_data, f, indent=2)

        print("\n" + "-" * 70)
        print("DELIVERABLES GENERATED:")
        print(f"   [Phase 3 Ready] Confirmed Polygons JSON: {polygon_json_path}")
        print(f"   [False-Positive Lab] Rejected Log JSON : {rejected_json_path}")
        print("=" * 70 + "\n")

        return {
            "status": "SUCCESS",
            "scene_id": scene_id,
            "total_candidates": len(candidates),
            "confirmed_count": len(confirmed_polygons),
            "rejected_count": len(rejected_candidates),
            "confirmed_polygons": polygon_dicts,
            "polygon_json_path": str(polygon_json_path),
            "rejected_json_path": str(rejected_json_path),
        }
