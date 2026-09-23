-- ================================================================
-- Demo seed data
-- All rows tagged with source = 'DEMO' for easy cleanup later.
-- Cleanup command: DELETE FROM vessels WHERE source = 'DEMO';
-- ================================================================

-- 1 scene (uses source_provider, not source — no tag needed)
INSERT INTO scenes (id, source_provider, external_scene_id, captured_at, footprint, storage_uri, sha256, processing_status)
VALUES (
  '11111111-1111-1111-1111-111111111111',
  'Sentinel-1',
  'S1_TEST_001',
  '2024-06-15 14:00:00+00',
  ST_GeomFromText('POLYGON((71.5 20.5, 73.5 20.5, 73.5 21.5, 71.5 21.5, 71.5 20.5))', 4326),
  's3://bucket/test.tif',
  'abc123def456abc123def456abc123def456abc123def456abc123def456abcd',
  'processed'
);

-- 1 spill
INSERT INTO spills (id, scene_id, detected_at, spill_polygon, area_sq_km, detection_model_name, detection_model_version, confidence_score, status)
VALUES (
  '22222222-2222-2222-2222-222222222222',
  '11111111-1111-1111-1111-111111111111',
  '2024-06-15 14:00:00+00',
  ST_GeomFromText('MULTIPOLYGON(((72.48 20.98, 72.52 20.98, 72.52 21.02, 72.48 21.02, 72.48 20.98)))', 4326),
  12.4,
  'UNet-ResNet34',
  'v1.0',
  0.87,
  'detected'
);

-- 3 vessels — source = 'DEMO' for easy cleanup
INSERT INTO vessels (id, mmsi, imo, vessel_name, vessel_type, flag_country_code, source)
VALUES
  ('33333333-3333-3333-3333-333333333331', '111111111', '9000001', 'MT SANMAR SONATA', 'crude_tanker',    'IN', 'DEMO'),
  ('33333333-3333-3333-3333-333333333332', '222222222', '9000002', 'MT OCEAN PRIDE',   'chemical_tanker', 'PA', 'DEMO'),
  ('33333333-3333-3333-3333-333333333333', '333333333', '9000003', 'MT GANGA STAR',    'crude_tanker',    'IN', 'DEMO');

-- 6 tracks — source = 'DEMO' for easy cleanup
INSERT INTO tracks (vessel_id, recorded_at, position, speed_knots, course_degrees, source, source_record_id)
VALUES
  ('33333333-3333-3333-3333-333333333331', '2024-06-15 05:30:00+00', ST_GeomFromText('POINT(72.35 20.90)', 4326), 12.0, 90,  'DEMO', 'demo_rec_001'),
  ('33333333-3333-3333-3333-333333333331', '2024-06-15 06:00:00+00', ST_GeomFromText('POINT(72.40 20.95)', 4326), 11.5, 88,  'DEMO', 'demo_rec_002'),
  ('33333333-3333-3333-3333-333333333332', '2024-06-15 08:00:00+00', ST_GeomFromText('POINT(72.25 20.98)', 4326), 0.5,  45,  'DEMO', 'demo_rec_003'),
  ('33333333-3333-3333-3333-333333333332', '2024-06-15 08:30:00+00', ST_GeomFromText('POINT(72.30 21.00)', 4326), 0.2,  90,  'DEMO', 'demo_rec_004'),
  ('33333333-3333-3333-3333-333333333333', '2024-06-15 03:30:00+00', ST_GeomFromText('POINT(72.55 20.75)', 4326), 10.0, 180, 'DEMO', 'demo_rec_005'),
  ('33333333-3333-3333-3333-333333333333', '2024-06-15 04:00:00+00', ST_GeomFromText('POINT(72.60 20.80)', 4326), 9.5,  175, 'DEMO', 'demo_rec_006');