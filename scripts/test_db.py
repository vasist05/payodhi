"""Test real DB adapters end-to-end."""
from datetime import datetime, timezone

if __name__ == "__main__":
    from adapters.read_spills import read_spill
    from adapters.read_candidates import read_candidates
    from adapters.write_drift_runs import write_drift_run

    # --- Read spill ---
    spill = read_spill("22222222-2222-2222-2222-222222222222")
    print("=== Spill ===")
    print(f"  ID:       {spill['spill_id']}")
    print(f"  Scene:    {spill['scene_id']}")
    print(f"  Centroid: ({spill['detection_lon']:.4f}, {spill['detection_lat']:.4f})")
    print(f"  Detected: {spill['detection_time']}")
    print(f"  Area:     {spill['area_km2']} km2")
    print(f"  Conf:     {spill['confidence']}")
    print(f"  SAR:      {spill['sar_source']}")
    print()

    # --- Read candidates ---
    win_start = datetime(2024, 6, 15, 2, 0, tzinfo=timezone.utc)
    win_end   = datetime(2024, 6, 15, 14, 0, tzinfo=timezone.utc)
    candidates = read_candidates(win_start, win_end)
    print(f"=== Candidates ({len(candidates)}) ===")
    for c in candidates:
        print(f"  {c['mmsi']} -- {c['vessel_name']}  ({c['vessel_type']})")
        print(f"    at ({c['lon']:.4f}, {c['lat']:.4f})  oil={c['oil_type']}")
        print(f"    vessel_id={c.get('vessel_id')}")
    print()

    # --- Write a test drift_run ---
    if candidates:
        test = candidates[0]
        run_id = write_drift_run({
            "spill_id": spill["spill_id"],
            "scene_id": spill["scene_id"],
            "vessel_mmsi": test["mmsi"],
            "vessel_id": test.get("vessel_id"),
            "mode": "forward",
            "oil_type_sampled": test["oil_type"],
            "release_time": test["release_time"],
            "detection_time": spill["detection_time"],
            "predicted_lon": 72.48,
            "predicted_lat": 20.99,
            "distance_km": 4.2,
            "forward_score": 0.86,
        })
        print(f"=== Wrote drift_run ===")
        print(f"  run_id: {run_id}")
    else:
        print("No candidates to write test drift_run")

    print()
    print("Real DB adapters OK.")