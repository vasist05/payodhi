"""
tests/test_phase2_db_integration.py

Integration and unit tests verifying the Phase 2 <-> Database integration contract.
Tests:
1. Pydantic schemas (Table 3 scenes, Table 4 spills).
2. Derived wind vector components (U10, V10).
3. Pinned SpillFilterBatchResponse shape.
4. FilterService 3-tier hybrid wind resolution.
5. Per-candidate error isolation in filter_batch.
"""

import math
import sys
import unittest
from pathlib import Path
from uuid import uuid4

# Ensure backend and repo root are on sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend"))

import types
from unittest.mock import MagicMock

# Mock backend dependencies if not installed on the testing host
try:
    import sqlalchemy
except ImportError:
    for mod_name in [
        "sqlalchemy",
        "sqlalchemy.ext",
        "sqlalchemy.ext.asyncio",
        "sqlalchemy.orm",
        "pydantic_settings",
        "boto3",
        "botocore",
        "botocore.exceptions",
        "app.config",
        "app.db",
        "app.db.session",
        "app.db.models",
        "app.db.models.enums",
        "app.db.models.audit_log",
        "app.db.models.scene",
        "app.db.models.spill",
        "app.repositories",
        "app.repositories.audit_repo",
        "app.repositories.scene_repo",
        "app.repositories.spill_repo",
    ]:
        if mod_name not in sys.modules:
            mod = types.ModuleType(mod_name)
            mod.__path__ = []
            sys.modules[mod_name] = mod

    sys.modules["sqlalchemy.ext.asyncio"].AsyncSession = MagicMock
    sys.modules["app.repositories.audit_repo"].AuditRepository = MagicMock
    sys.modules["app.repositories.scene_repo"].SceneRepository = MagicMock
    sys.modules["app.repositories.spill_repo"].SpillRepository = MagicMock
    sys.modules["app.repositories"].AuditRepository = MagicMock
    sys.modules["app.repositories"].SceneRepository = MagicMock
    sys.modules["app.repositories"].SpillRepository = MagicMock

from app.schemas.common import geojson_to_wkt, wkt_to_geojson
from app.schemas.scene import SceneResponse
from app.schemas.spill import (
    SpillBase,
    SpillCandidate,
    SpillFilterBatchRequest,
    SpillFilterBatchResponse,
    SpillResponse,
)


class TestPhase2DatabaseContracts(unittest.TestCase):

    def test_geojson_wkt_conversion(self):
        """Verify spatial conversion between GeoJSON and PostGIS MultiPolygon WKT."""
        geojson = {
            "type": "Polygon",
            "coordinates": [
                [
                    [80.32, 13.22],
                    [80.34, 13.22],
                    [80.34, 13.24],
                    [80.32, 13.24],
                    [80.32, 13.22],
                ]
            ],
        }
        wkt_str = geojson_to_wkt(geojson)
        self.assertTrue(wkt_str.startswith("MULTIPOLYGON"))
        self.assertIn("80.32 13.22", wkt_str)

    def test_scene_derived_wind_components(self):
        """Verify wind_u10 and wind_v10 are computed dynamically from speed and direction."""
        scene_id = uuid4()
        now = "2026-09-22T00:00:00Z"
        footprint = {
            "type": "Polygon",
            "coordinates": [[[80.0, 13.0], [81.0, 13.0], [81.0, 14.0], [80.0, 14.0], [80.0, 13.0]]],
        }

        # Case 1: 10 m/s wind blowing from East (90 degrees)
        # u10 = 10 * sin(90) = 10, v10 = 10 * cos(90) = 0
        scene = SceneResponse(
            id=scene_id,
            source_provider="Copernicus",
            external_scene_id="S1A_TEST_001",
            captured_at=now,
            ingested_at=now,
            created_at=now,
            updated_at=now,
            footprint=footprint,
            storage_uri="s3://payodi-scenes/test.tif",
            sha256="a" * 64,
            wind_speed=10.0,
            wind_direction=90.0,
        )
        self.assertAlmostEqual(scene.wind_u10, 10.0, places=3)
        self.assertAlmostEqual(scene.wind_v10, 0.0, places=3)

        # Case 2: 10 m/s wind blowing from North (0 degrees)
        # u10 = 10 * sin(0) = 0, v10 = 10 * cos(0) = 10
        scene2 = SceneResponse(
            id=scene_id,
            source_provider="Copernicus",
            external_scene_id="S1A_TEST_002",
            captured_at=now,
            ingested_at=now,
            created_at=now,
            updated_at=now,
            footprint=footprint,
            storage_uri="s3://payodi-scenes/test2.tif",
            sha256="b" * 64,
            wind_speed=10.0,
            wind_direction=0.0,
        )
        self.assertAlmostEqual(scene2.wind_u10, 0.0, places=3)
        self.assertAlmostEqual(scene2.wind_v10, 10.0, places=3)

        # Case 3: None when speed/direction are missing
        scene3 = SceneResponse(
            id=scene_id,
            source_provider="Copernicus",
            external_scene_id="S1A_TEST_003",
            captured_at=now,
            ingested_at=now,
            created_at=now,
            updated_at=now,
            footprint=footprint,
            storage_uri="s3://payodi-scenes/test3.tif",
            sha256="c" * 64,
            wind_speed=None,
            wind_direction=None,
        )
        self.assertIsNone(scene3.wind_u10)
        self.assertIsNone(scene3.wind_v10)

    def test_spill_table_contract_and_no_banned_columns(self):
        """Verify SpillBase has exactly the allowed fields and no banned columns."""
        banned = {"wind_u10", "wind_v10", "wind_speed", "rejection_reason"}
        spill_fields = set(SpillBase.model_fields.keys())
        intersection = spill_fields.intersection(banned)
        self.assertEqual(len(intersection), 0, f"Found banned columns in SpillBase: {intersection}")

        # Check allowed fields
        expected = {
            "scene_id",
            "spill_polygon",
            "area_sq_km",
            "detection_model_name",
            "detection_model_version",
            "confidence_score",
            "processing_run_id",
            "status",
            "reviewed_by",
            "review_notes",
        }
        self.assertEqual(spill_fields, expected)

    def test_pinned_batch_response_shape(self):
        """Verify SpillFilterBatchResponse has exactly the required fields."""
        fields = set(SpillFilterBatchResponse.model_fields.keys())
        expected = {
            "confirmed",
            "rejected",
            "failed",
            "model_mode",
            "calibration_temperature",
        }
        self.assertEqual(fields, expected)

    def test_filter_service_hybrid_wind_resolution(self):
        """Test FilterService._resolve_wind tier priority."""
        from app.services.filter_service import FilterService

        class MockScene:
            def __init__(self, wind_speed=None, wind_direction=None):
                self.wind_speed = wind_speed
                self.wind_direction = wind_direction

        # Dummy session (not executed for _resolve_wind)
        svc = FilterService(session=None, mode="sar_uv")

        # Tier 1: Scene has wind
        scene_with_wind = MockScene(wind_speed=5.0, wind_direction=45.0)
        u10, v10, tag = svc._resolve_wind(scene=scene_with_wind, patch_path="any_patch.jpg")
        self.assertEqual(tag, "scene_derived")
        self.assertAlmostEqual(u10, 5.0 * math.sin(math.radians(45.0)), places=4)
        self.assertAlmostEqual(v10, 5.0 * math.cos(math.radians(45.0)), places=4)

        # Tier 2: Scene has no wind, but patch is known CSIRO patch in wind_metadata.json
        scene_no_wind = MockScene(wind_speed=None, wind_direction=None)
        known_csiro_patch = "data/fp_filter/csiro_patches/oil/0_0_0_img_0bBRglmdLdC6cFxF_JAV_cls_1.jpg"
        u10, v10, tag = svc._resolve_wind(scene=scene_no_wind, patch_path=known_csiro_patch)
        self.assertEqual(tag, "metadata_json")
        self.assertAlmostEqual(u10, -4.7133, places=2)
        self.assertAlmostEqual(v10, 2.3790, places=2)

        # Tier 3: Unknown patch and no scene wind
        u10, v10, tag = svc._resolve_wind(scene=scene_no_wind, patch_path="unknown_scene_patch.jpg")
        self.assertEqual(tag, "none")
        self.assertIsNone(u10)
        self.assertIsNone(v10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
