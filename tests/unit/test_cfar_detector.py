# tests/unit/test_cfar_detector.py
import unittest
import numpy as np

try:
    from core.phase4_ais.cfar_detector import ca_cfar, detect_sar_ships
except ImportError:
    from backend.ais_pipeline.cfar_detector import ca_cfar, detect_sar_ships


class TestCfarDetector(unittest.TestCase):
    def test_cfar_basic_detection(self):
        img = np.zeros((10, 10), dtype=float)
        img[5, 5] = 0.9
        detections = ca_cfar(img, guard_cells=1, training_cells=2, threshold_factor=4.0)
        self.assertTrue(detections[5, 5])
        self.assertEqual(detections.sum(), 1)

    def test_cfar_empty_input(self):
        img = np.zeros((0, 0))
        detections = ca_cfar(img)
        self.assertEqual(detections.size, 0)

    def test_cfar_nan_handling(self):
        img = np.full((5, 5), np.nan)
        detections = ca_cfar(img)
        self.assertFalse(detections.any())

    def test_detect_sar_ships_no_ships(self):
        ais = []
        res = detect_sar_ships(sar_image_path="non_existent.tif", ais_targets=ais)
        self.assertIsInstance(res, list)

    def test_cfar_cluster_merging(self):
        from core.phase4_ais.cfar_detector import cluster_detections
        det_mask = np.zeros((20, 20), dtype=bool)
        # 3 adjacent pixels (should form 1 cluster)
        det_mask[10, 10] = True
        det_mask[10, 11] = True
        det_mask[11, 10] = True
        clusters = cluster_detections(det_mask)
        self.assertEqual(len(clusters), 1)
        r, c, area = clusters[0]
        self.assertEqual(area, 3)
        self.assertAlmostEqual(r, 31.0 / 3.0, places=3)
        self.assertAlmostEqual(c, 31.0 / 3.0, places=3)


if __name__ == '__main__':
    unittest.main()
