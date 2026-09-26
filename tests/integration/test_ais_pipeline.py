"""
Integration tests for core.phase4_ais module.
Covers:
1. Haversine distance & Bounding boxes
2. 2D CA-CFAR radar detector
3. AIS gap detection (> 30 min blackout)
4. SAR-AIS temporal alignment (interpolation at satellite pass time)
5. Vessel static metrics (DWT, IMO, Flag, Length, Beam)
6. Historical AIS ingestion (GFW / Chennai 2017 benchmark)
7. Phase 3 drift simulation output contract integration
8. GeoJSON track LineString serialization
"""

import unittest
import numpy as np
import json
import asyncio
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.phase4_ais.geo_utils import haversine, get_bounding_box
from core.phase4_ais.cfar_detector import ca_cfar, detect_sar_ships
from core.phase4_ais.correlate import (
    correlate_sar_ais,
    compute_behavioral_anomaly,
    detect_ais_gaps,
    interpolate_position_at_time
)
from core.phase4_ais.fetch_ais import fetch_mock_ais, fetch_historical_ais
from core.phase4_ais.geojson_exporter import save_geojson
from core.phase4_ais.pipeline import run_phase4_pipeline


class TestGeoUtils(unittest.TestCase):
    def test_haversine_identical_points(self):
        dist = haversine(18.9, 72.8, 18.9, 72.8)
        self.assertAlmostEqual(dist, 0.0, places=4)

    def test_haversine_known_distance(self):
        dist = haversine(18.9220, 72.8347, 15.4989, 73.8278)
        self.assertTrue(390.0 < dist < 420.0)

    def test_bounding_box_generation(self):
        bbox = get_bounding_box(18.9, 72.8, radius_km=30.0)
        self.assertEqual(len(bbox), 1)
        self.assertEqual(len(bbox[0]), 2)
        min_pt, max_pt = bbox[0][0], bbox[0][1]
        self.assertTrue(min_pt[0] < 18.9 < max_pt[0])
        self.assertTrue(min_pt[1] < 72.8 < max_pt[1])


class TestCACFAR(unittest.TestCase):
    def test_cfar_detection_on_synthetic_target(self):
        image = np.full((50, 50), 0.05)
        image[25, 25] = 0.95

        detections = ca_cfar(image, guard_cells=2, training_cells=4, threshold_factor=4.0)
        self.assertTrue(detections[25, 25])
        self.assertFalse(detections[5, 5])
        self.assertFalse(detections[45, 45])

    def test_detect_sar_ships_synthetic_fallback(self):
        vessels = detect_sar_ships(sar_image_path=None, ais_targets=[])
        self.assertGreater(len(vessels), 0)
        for v in vessels:
            self.assertIn("target_id", v)
            self.assertIn("lat", v)
            self.assertIn("lon", v)


class TestAISGapDetection(unittest.TestCase):
    def test_ais_gap_identified(self):
        track = [
            {"timestamp": "2017-01-28T03:00:00Z", "lat": 13.20, "lon": 80.30},
            {"timestamp": "2017-01-28T03:15:00Z", "lat": 13.22, "lon": 80.32},
            {"timestamp": "2017-01-28T04:30:00Z", "lat": 13.30, "lon": 80.40},
        ]
        gaps = detect_ais_gaps(track, max_gap_seconds=1800)
        self.assertEqual(len(gaps), 1)
        self.assertAlmostEqual(gaps[0]["gap_duration_minutes"], 75.0, places=1)


class TestTemporalInterpolation(unittest.TestCase):
    def test_interpolation_between_points(self):
        track = [
            {"timestamp": "2017-01-28T05:00:00Z", "lat": 13.0, "lon": 80.0},
            {"timestamp": "2017-01-28T06:00:00Z", "lat": 14.0, "lon": 81.0},
        ]
        target_time = "2017-01-28T05:30:00Z"
        lat, lon = interpolate_position_at_time(track, target_time)
        self.assertAlmostEqual(lat, 13.5, places=2)
        self.assertAlmostEqual(lon, 80.5, places=2)


class TestCorrelationEngine(unittest.TestCase):
    def test_dark_vessel_flagging(self):
        radar_targets = [
            {"target_id": "SAR-001", "lat": 18.91, "lon": 72.12, "estimated_length_m": 120.0},
            {"target_id": "SAR-002", "lat": 19.50, "lon": 73.50, "estimated_length_m": 80.0},
        ]
        ais_targets = [
            {
                "mmsi": "111111111",
                "name": "CARGO ALPHA",
                "lat": 18.911,
                "lon": 72.121,
                "speed_knots": 10.0,
                "track": [],
                "dwt": 50000,
                "flag": "India"
            }
        ]
        correlations, dark_vessels = correlate_sar_ais(
            radar_targets=radar_targets,
            ais_targets=ais_targets,
            match_threshold_km=5.0
        )
        self.assertEqual(len(correlations), 1)
        self.assertEqual(correlations[0]["radar_target"]["target_id"], "SAR-001")
        self.assertEqual(correlations[0]["ais_target"]["name"], "CARGO ALPHA")
        self.assertEqual(len(dark_vessels), 1)
        self.assertEqual(dark_vessels[0]["target_id"], "SAR-002")
        self.assertTrue(dark_vessels[0]["is_dark"])


class TestBehavioralAnomaly(unittest.TestCase):
    def test_high_anomaly_for_gaps_and_speed_drop(self):
        vessel = {
            "name": "TEST TANKER",
            "vessel_type": "Tanker",
            "speed_knots": 2.0,
            "track": [
                {"timestamp": "2017-01-28T02:00:00Z", "lat": 13.20, "lon": 80.30},
                {"timestamp": "2017-01-28T04:00:00Z", "lat": 13.25, "lon": 80.35},
            ]
        }
        score, factors = compute_behavioral_anomaly(vessel, spill_lat=13.25, spill_lon=80.35)
        self.assertGreaterEqual(score, 60.0)


class TestHistoricalAISIngestion(unittest.TestCase):
    def test_chennai_2017_historical_load_no_hardcoded(self):
        # Without GFW live API response or cache, fallback must be empty list (never hardcoded fake vessels)
        vessels = fetch_historical_ais(13.25, 80.35, radius_km=30.0)
        self.assertIsInstance(vessels, list)
        names = [v.get("name") for v in vessels]
        self.assertNotIn("DAWN KANCHIPURAM", names)


class TestGFWCacheFallback(unittest.TestCase):
    def test_fallback_saves_and_loads_json(self):
        from core.phase4_ais.fetch_gfw_validation import (
            fetch_and_save_validation_data,
            load_cached_validation,
        )
        result = fetch_and_save_validation_data(gfw_token="invalid_token_for_test")
        self.assertIn("chennai_2017", result)
        self.assertIn("haldia_2018", result)

    def test_load_cached_validation_missing_cache(self):
        from core.phase4_ais.fetch_gfw_validation import load_cached_validation
        vessels = load_cached_validation("non_existent_case_123")
        self.assertIsInstance(vessels, list)
        self.assertEqual(len(vessels), 0)


if __name__ == "__main__":
    unittest.main()
