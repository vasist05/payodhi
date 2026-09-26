# tests/unit/test_geo_utils.py
import unittest
import math

try:
    from core.phase4_ais.geo_utils import haversine, get_bounding_box
except ImportError:
    from backend.ais_pipeline.geo_utils import haversine, get_bounding_box


class TestGeoUtils(unittest.TestCase):
    def test_haversine_zero(self):
        self.assertAlmostEqual(haversine(0, 0, 0, 0), 0.0, places=5)

    def test_haversine_known(self):
        # Approx distance between (0,0) and (0,1) should be ~111.19 km
        dist = haversine(0, 0, 0, 1)
        self.assertAlmostEqual(dist, 111.19, delta=0.5)

    def test_haversine_negative(self):
        d1 = haversine(-10, -20, -10, -20)
        d2 = haversine(10, 20, 10, 20)
        self.assertAlmostEqual(d1, 0.0, places=5)
        self.assertAlmostEqual(d2, 0.0, places=5)

    def test_bounding_box_limits(self):
        lat, lon = 10.0, 20.0
        radius = 10.0
        bbox = get_bounding_box(lat, lon, radius)
        self.assertEqual(len(bbox), 1)
        [[lat_min, lon_min], [lat_max, lon_max]] = bbox[0]
        self.assertLessEqual(lat_min, lat)
        self.assertGreaterEqual(lat_max, lat)
        self.assertLessEqual(lon_min, lon)
        self.assertGreaterEqual(lon_max, lon)

    def test_boundary_edge(self):
        # Points exactly on 5 km boundary should be considered within radius
        lat, lon = 0.0, 0.0
        delta_lat = (5.0 / 6371.0) * (180.0 / math.pi)
        point_lat = lat + delta_lat
        point_lon = lon
        self.assertAlmostEqual(haversine(lat, lon, point_lat, point_lon), 5.0, places=1)


if __name__ == '__main__':
    unittest.main()
