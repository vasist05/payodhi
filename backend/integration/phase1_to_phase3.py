"""
Bridge: Phase 1 -> Phase 2 -> Phase 3 Integration.
Routes candidate detections through the Phase 2 False-Positive Filter before outputting to Phase 3.
"""

from typing import Any, Dict, List, Optional
from backend.integration.pipeline_p1_p2_p3 import IntegratedSpillPipeline


class Phase1ToPhase3Bridge:
    """
    Bridge integrating Phase 1 detection, Phase 2 false-positive filtering,
    and Phase 3 drift polygon generation.
    """

    def __init__(self, output_dir: str = "data/processed/polygons", mode: str = "sar_uv"):
        self.pipeline = IntegratedSpillPipeline(
            fp_filter_mode=mode,
            polygons_dir=output_dir,
        )

    def process_scene(self, scene_path: str, scene_meta: Optional[dict] = None) -> str:
        """
        Processes SAR scene through Phase 1 segmentation + Phase 2 filtering.
        Returns the path to the verified polygon JSON file for Phase 3.
        """
        results = self.pipeline.process_scene(scene_path=scene_path, scene_meta=scene_meta)
        return results.get("polygon_json_path", "")

    def get_polygons(self, scene_path: str, scene_meta: Optional[dict] = None) -> List[dict]:
        """
        Returns confirmed polygon dictionaries directly.
        """
        results = self.pipeline.process_scene(scene_path=scene_path, scene_meta=scene_meta)
        return results.get("confirmed_polygons", [])
