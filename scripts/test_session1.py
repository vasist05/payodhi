from datetime import datetime, timezone
from adapters.read_spills import read_spill
from adapters.read_candidates import read_candidates
from adapters.read_environmental import read_environmental
from adapters.write_drift_runs import write_drift_run


spill = read_spill("spill_001")
print("=== Spill ===")
print(f"  spill_id:    {spill['spill_id']}")
print(f"  centroid:    ({spill['centroid_lon']}, {spill['centroid_lat']})")
print(f"  detection:   {spill['detection_time']}")
print(f"  is_oil:      {spill['is_oil']}")
print(f"  sar_source:  {spill['sar_source']}")
print()

win_start = datetime(2024, 6, 15, 2, 0, tzinfo=timezone.utc)
win_end   = datetime(2024, 6, 15, 14, 0, tzinfo=timezone.utc)
candidates = read_candidates(win_start, win_end)
print(f"=== Candidates ({len(candidates)}) ===")
for c in candidates:
    print(f"  {c['mmsi']} -- {c['vessel_name']} at ({c['lon']}, {c['lat']})")
print()

env = read_environmental("scene_001")
print("=== Environmental ===")
print(f"  wind:     {env['wind_file']}")
print(f"  current:  {env['current_file']}")
print(f"  wave:     {env.get('wave_file')}")
print()

run_id = write_drift_run({
    "spill_id": "spill_001",
    "vessel_mmsi": "111111111",
    "mode": "forward",
    "oil_type_sampled": "GENERIC HEAVY CRUDE",
    "release_time": "2024-06-15T06:00:00Z",
    "detection_time": "2024-06-15T14:00:00Z",
    "predicted_lon": 72.48,
    "predicted_lat": 20.99,
    "distance_km": 4.2,
    "forward_score": 0.86,
})
print(f"=== Wrote drift_run ===")
print(f"  run_id: {run_id}")
print()
print("Session 1 OK")