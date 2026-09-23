"""
tests/test_phase1_detection.py

Unit and integration tests for Phase 1 SAR Oil Spill Detection.
Tests:
1. Preprocessing & Normalization (0-255 -> [0.0, 1.0], bounding box + 32px padding, spill fraction).
2. PyTorch U-Net architecture & checkpoint loading (base_model_kaggle_iou7441.pth).
3. Sliding-window tiler and overlap blending reconstruction.
4. Post-processing, vectorization (GeoJSON MultiPolygon), area calculation, and candidate extraction.
5. Detection API schemas (DetectionRunRequest, DetectionRunResponse).
"""

import sys
import unittest
from pathlib import Path
from uuid import uuid4

import numpy as np
import torch

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend"))

from core.phase1_sar.model import SARUNetDetector, load_detection_model
from core.phase1_sar.postprocess import (
    clean_binary_mask,
    compute_geodesic_area_sq_km,
    create_spill_candidates,
    pixel_to_geo,
    vectorize_mask,
)
from core.phase1_sar.preprocessing import (
    check_spill_fraction,
    crop_and_resize,
    find_spill_bounding_box,
    load_and_normalize_sar,
)
from core.phase1_sar.tiler import SceneTiler, generate_tiles, get_blend_weight_mask


class TestPhase1Preprocessing(unittest.TestCase):

    def test_normalization(self):
        arr_uint8 = np.array([[0, 127], [255, 64]], dtype=np.uint8)
        norm = load_and_normalize_sar(arr_uint8)
        self.assertEqual(norm.dtype, np.float32)
        self.assertAlmostEqual(float(norm[0, 0]), 0.0)
        self.assertAlmostEqual(float(norm[1, 0]), 1.0)
        self.assertAlmostEqual(float(norm[0, 1]), 127 / 255.0, places=3)

    def test_bounding_box_extraction(self):
        # 256x256 image with spill between (50, 50) and (100, 100)
        mask = np.zeros((256, 256), dtype=np.uint8)
        mask[50:101, 50:101] = 255

        bbox = find_spill_bounding_box(mask, padding=32, threshold=127)
        self.assertIsNotNone(bbox)
        y0, y1, x0, x1 = bbox
        # With 32px padding: y0 = 50-32=18, y1 = 100+32+1 = 133
        self.assertEqual(y0, 18)
        self.assertEqual(x0, 18)
        self.assertEqual(y1, 133)
        self.assertEqual(x1, 133)

    def test_spill_fraction_verification(self):
        # 100x100 mask = 10,000 pixels
        mask = np.zeros((100, 100), dtype=np.float32)
        # 4% oil = 400 pixels (< 5% threshold)
        mask[:20, :20] = 1.0
        valid, frac = check_spill_fraction(mask, min_fraction=0.05, threshold=0.5)
        self.assertFalse(valid)
        self.assertAlmostEqual(frac, 0.04)

        # 10% oil = 1000 pixels (> 5% threshold)
        mask[:50, :20] = 1.0
        valid, frac = check_spill_fraction(mask, min_fraction=0.05, threshold=0.5)
        self.assertTrue(valid)
        self.assertAlmostEqual(frac, 0.10)

    def test_crop_and_resize(self):
        img = np.ones((500, 500), dtype=np.float32)
        bbox = (50, 150, 50, 150)
        crop = crop_and_resize(img, bbox, target_size=(256, 256))
        self.assertEqual(crop.shape, (256, 256))


class TestPhase1ModelAndTiler(unittest.TestCase):

    def test_checkpoint_load_and_forward(self):
        ckpt_path = root_dir / "base_model_kaggle_iou7441.pth"
        if not ckpt_path.exists():
            self.skipTest("base_model_kaggle_iou7441.pth not found in repo root")

        model = load_detection_model(checkpoint_path=ckpt_path, device="cpu")
        self.assertIsInstance(model, SARUNetDetector)

        # Forward pass on standard 256x256 patch
        dummy = torch.randn(1, 1, 256, 256)
        prob = model.predict_proba(dummy)
        self.assertEqual(prob.shape, (1, 1, 256, 256))
        self.assertTrue(torch.all(prob >= 0.0) and torch.all(prob <= 1.0))

    def test_tiler_coverage_and_blend(self):
        # 512x512 image tiled with 256 window and 192 stride
        tiles = generate_tiles(512, 512, tile_size=256, stride=192)
        self.assertGreater(len(tiles), 4)

        w = get_blend_weight_mask(tile_size=256)
        self.assertEqual(w.shape, (256, 256))
        # Center weight should be higher than corner weight
        self.assertGreater(w[128, 128], w[0, 0])


class TestPhase1PostProcessing(unittest.TestCase):

    def test_vectorization_and_candidate_creation(self):
        # Create 512x512 mask with circular slick
        prob_map = np.zeros((512, 512), dtype=np.float32)
        y, x = np.ogrid[:512, :512]
        dist_from_center = np.sqrt((x - 250)**2 + (y - 250)**2)
        prob_map[dist_from_center <= 30] = 0.95  # circular oil slick

        clean_mask = clean_binary_mask(prob_map, threshold=0.5, min_pixels=50)
        self.assertGreater(clean_mask.sum(), 0)

        dets = vectorize_mask(
            clean_mask,
            prob_map,
            bbox_wgs84=(71.0, 18.5, 72.0, 19.5),
            min_pixels=50,
        )
        self.assertEqual(len(dets), 1)

        d = dets[0]
        self.assertEqual(d["geometry"]["type"], "MultiPolygon")
        self.assertGreater(d["area_sq_km"], 0.0)
        self.assertAlmostEqual(d["confidence"], 0.95, places=2)

        # Create SpillCandidates
        candidates = create_spill_candidates(
            dets,
            raw_image_2d=prob_map,
            scene_id=str(uuid4()),
            output_dir=None,  # in-memory only
        )
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertAlmostEqual(c.detection_confidence, 0.95, places=2)
        self.assertIn("spill_polygon", c.metadata)


class TestPhase1Schemas(unittest.TestCase):

    def test_detection_schemas(self):
        from app.schemas.detection import DetectionRunRequest, DetectionRunResponse

        req = DetectionRunRequest(
            scene_id=uuid4(),
            threshold=0.55,
            min_pixels=100,
        )
        self.assertEqual(req.threshold, 0.55)
        self.assertEqual(req.min_pixels, 100)

        resp = DetectionRunResponse(
            scene_id=req.scene_id,
            spill_count=0,
            spills=[],
            candidates=[],
            status="success",
            message="No spills",
        )
        self.assertEqual(resp.spill_count, 0)
        self.assertEqual(resp.status, "success")


if __name__ == "__main__":
    unittest.main()
