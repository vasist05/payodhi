-- ================================================================
-- Remove all demo seed data
-- Safe to run anytime. Deletes ONLY rows tagged source='DEMO'.
-- Real data (source='AIS' or other) is untouched.
-- ================================================================

-- Show what will be removed
SELECT 'tracks'   AS table_name, COUNT(*) AS rows_to_delete FROM tracks   WHERE source = 'DEMO'
UNION ALL
SELECT 'vessels',              COUNT(*)                     FROM vessels  WHERE source = 'DEMO';

-- Delete (CASCADE removes dependent rows automatically)
DELETE FROM tracks  WHERE source = 'DEMO';
DELETE FROM vessels WHERE source = 'DEMO';

-- Confirm
SELECT 'vessels' AS table_name, COUNT(*) AS remaining FROM vessels WHERE source = 'DEMO';