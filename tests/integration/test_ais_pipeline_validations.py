import unittest
import json
import datetime
from unittest import mock
from pathlib import Path
import sys
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Modules under test
from core.phase4_ais import geo_utils, cfar_detector, fetch_ais, correlate, geojson_exporter

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURE_DIR.mkdir(exist_ok=True)

SAMPLE_SAR_SHIPS = [
    {"sar_id": 1, "lat": 13.5, "lon": 80.3, "intensity": 0.95},
    {"sar_id": 2, "lat": 13.6, "lon": 80.35, "intensity": 0.90},
]


class TestGeoUtils(unittest.TestCase):
    def test_haversine_zero(self):
        self.assertAlmostEqual(geo_utils.haversine(0, 0, 0, 0), 0.0, places=5)

    def test_haversine_known_distance(self):
        dist = geo_utils.haversine(18.96, 72.83, 13.08, 80.27)
        self.assertAlmostEqual(dist, 1030, delta=5)

    def test_haversine_antipodes(self):
        dist = geo_utils.haversine(0, 0, 0, 180)
        self.assertAlmostEqual(dist, 20015, delta=100)

    def test_haversine_equator(self):
        dist = geo_utils.haversine(0, 0, 0, 10)
        self.assertAlmostEqual(dist, 1110, delta=20)

    def test_haversine_pole(self):
        dist = geo_utils.haversine(90, 0, 80, 0)
        self.assertAlmostEqual(dist, 1110, delta=20)

    def test_bounding_box(self):
        box = geo_utils.get_bounding_box(13.0, 80.0, 10)
        self.assertEqual(len(box), 1)
        [[lat_min, lon_min], [lat_max, lon_max]] = box[0]
        self.assertLess(lat_min, lat_max)
        self.assertLess(lon_min, lon_max)


class TestCA_CFAR(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((10, 10), dtype=float)
        self.image[5, 5] = 0.95

    def test_ca_cfar_detection(self):
        det = cfar_detector.ca_cfar(self.image, guard_cells=1, training_cells=2, threshold_factor=4.0)
        self.assertTrue(det[5, 5])
        self.assertEqual(det.sum(), 1)

    def test_cluster_detections(self):
        det = np.zeros((10, 10), dtype=bool)
        det[2, 2] = True
        det[2, 3] = True
        clusters = cfar_detector.cluster_detections(det)
        self.assertEqual(len(clusters), 1)
        r, c, area = clusters[0]
        self.assertEqual(area, 2)
        self.assertAlmostEqual(r, 2.0)
        self.assertAlmostEqual(c, 2.5)

    def test_detect_sar_ships_synthetic(self):
        ships = cfar_detector.detect_sar_ships(None, ais_targets=[])
        self.assertIsInstance(ships, list)
        self.assertGreater(len(ships), 0)


class TestCorrelate(unittest.TestCase):
    def setUp(self):
        self.sar_ships = [
            {"target_id": "SAR-1", "lat": 13.0, "lon": 80.0},
            {"target_id": "SAR-2", "lat": 14.0, "lon": 81.0},
        ]
        self.ais_targets = [
            {"mmsi": "111", "name": "Vessel A", "lat": 13.01, "lon": 80.01, "speed_knots": 10, "track": []},
            {"mmsi": "222", "name": "Vessel B", "lat": 15.0, "lon": 82.0, "speed_knots": 12, "track": []},
        ]

    def test_correlate_sar_ais(self):
        matches, dark = correlate.correlate_sar_ais(self.sar_ships, self.ais_targets, match_threshold_km=5.0)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["radar_target"]["target_id"], "SAR-1")
        self.assertEqual(matches[0]["ais_target"]["mmsi"], "111")
        self.assertEqual(len(dark), 1)
        self.assertEqual(dark[0]["target_id"], "SAR-2")

    def test_detect_ais_gaps(self):
        track = [
            {"timestamp": "2020-01-01T00:00:00Z", "lat": 10.0, "lon": 20.0},
            {"timestamp": "2020-01-01T00:10:00Z", "lat": 10.05, "lon": 20.05},
            {"timestamp": "2020-01-01T01:00:00Z", "lat": 10.1, "lon": 20.1},
        ]
        gaps = correlate.detect_ais_gaps(track, max_gap_seconds=1800)
        self.assertEqual(len(gaps), 1)
        self.assertAlmostEqual(gaps[0]["gap_duration_minutes"], 50.0)

    def test_interpolate_position_at_time(self):
        track = [
            {"timestamp": "2020-01-01T00:00:00Z", "lat": 10.0, "lon": 20.0},
            {"timestamp": "2020-01-01T01:00:00Z", "lat": 12.0, "lon": 22.0},
        ]
        lat, lon = correlate.interpolate_position_at_time(track, "2020-01-01T00:30:00Z")
        self.assertAlmostEqual(lat, 11.0)
        self.assertAlmostEqual(lon, 21.0)

    def test_compute_behavioral_anomaly(self):
        vessel = {
            "name": "TEST",
            "vessel_type": "Tanker",
            "speed_knots": 1.0,
            "track": [
                {"timestamp": "2020-01-01T00:00:00Z", "lat": 10.0, "lon": 20.0},
                {"timestamp": "2020-01-01T02:00:00Z", "lat": 10.02, "lon": 20.02},
            ]
        }
        score, factors = correlate.compute_behavioral_anomaly(vessel, spill_lat=10.0, spill_lon=20.0)
        self.assertGreaterEqual(score, 50.0)


class TestGeoJSONExporter(unittest.TestCase):
    def test_export_geojson(self):
        sar = [{"target_id": "S1", "lat": 10.0, "lon": 20.0}]
        ais = [{"name": "A1", "lat": 10.01, "lon": 20.01, "track": []}]
        matches = [{"radar_target": sar[0], "ais_target": ais[0], "distance_km": 1.5}]
        dark = []
        out = geojson_exporter.to_geojson(
            correlations=matches,
            dark_vessels=dark,
            all_ais_vessels=ais,
            spill_lat=10.0,
            spill_lon=20.0
        )
        self.assertIn("type", out)
        self.assertEqual(out["type"], "FeatureCollection")
        self.assertGreater(len(out["features"]), 0)


if __name__ == "__main__":
    unittest.main()
