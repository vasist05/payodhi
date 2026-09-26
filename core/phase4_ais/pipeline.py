"""
Main Orchestration Pipeline for Phase 4: AIS Correlation & Dark Vessel Detection.
Integrates with Phase 3 Drift Simulation outputs, real Sentinel-1 GeoTIFFs,
Global Fishing Watch historical archives, and temporal track alignment.

New CLI flags (v2):
  --aoi              [mumbai_high|chennai_ennore|gulf_of_kutch|haldia_sundarbans]
  --start-date       YYYY-MM-DD  (GFW historical window start)
  --end-date         YYYY-MM-DD  (GFW historical window end)
"""

import os
import json
import argparse
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional


from .geo_utils import INDIAN_AOIS
from .fetch_ais import fetch_live_ais, fetch_mock_ais, fetch_historical_ais
from .cfar_detector import detect_sar_ships
from .correlate import correlate_sar_ais
from .geojson_exporter import save_geojson


async def run_phase4_pipeline(
    spill_lat: float = 18.90,
    spill_lon: float = 72.10,
    radius_km: float = 150.0,
    match_threshold_km: float = 5.0,
    listen_seconds: int = 30,
    use_mock: bool = False,
    use_historical: bool = False,
    use_validation_cases: bool = False,
    validation_dir: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sar_file: Optional[str] = None,
    sar_time: Optional[str] = None,
    gfw_token: Optional[str] = None,
    phase3_output: Optional[Dict[str, Any]] = None,
    output_geojson: str = "core/phase4_ais/phase4_output.geojson",
    ais_ships: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:

    """
    Executes the comprehensive Phase 4 pipeline.

    Args:
        spill_lat: Estimated spill centroid latitude (or from Phase 3).
        spill_lon: Estimated spill centroid longitude (or from Phase 3).
        radius_km: AIS search corridor radius around origin.
        match_threshold_km: Maximum association distance between radar target and AIS transponder.
        listen_seconds: Duration to collect live WebSocket AIS messages.
        use_mock: If True, uses deterministic simulated fleet with tracks.
        use_historical: If True, queries Global Fishing Watch API or historical incident archive.
        start_date: Historical window start date (YYYY-MM-DD), used with --historical.
        end_date: Historical window end date (YYYY-MM-DD), used with --historical.
        sar_file: Path to real Sentinel-1 GeoTIFF (.tif) file.
        sar_time: SAR satellite acquisition timestamp (ISO 8601 UTC).
        gfw_token: Global Fishing Watch API token.
        phase3_output: Structured output dictionary from Phase 3 Drift Simulation.
        output_geojson: Destination file path for GeoJSON vector export.
        ais_ships: Optional pre-loaded list of AIS vessels.

    Returns:
        Structured dictionary containing correlated fleet, dark vessel alerts, and GeoJSON payload.
    """
    # Integrate Phase 3 Output Contract if provided
    if phase3_output:
        print("\n[PHASE 3 INTEGRATION] Consuming upstream drift simulation contract...")
        spill_lat = phase3_output.get("origin_lat", spill_lat)
        spill_lon = phase3_output.get("origin_lon", spill_lon)
        if "sar_acquisition_time" in phase3_output:
            sar_time = phase3_output["sar_acquisition_time"]
        if "release_window" in phase3_output:
            rw = phase3_output["release_window"]
            print(f"   Drift Release Window: {rw.get('start_time')} -> {rw.get('end_time')}")

    print("=" * 65)
    print("  PHASE 4: AIS INGESTION, CA-CFAR & DARK VESSEL CORRELATION")
    print("=" * 65)
    print(f"  Operational Origin: ({spill_lat:.4f} N, {spill_lon:.4f} E)")
    print(f"  Corridor Radius:    {radius_km} km")
    print(f"  Match Threshold:    {match_threshold_km} km")
    if sar_time:
        print(f"  SAR Timestamp:      {sar_time} (Temporal Alignment Anchor)")
    if sar_file:
        print(f"  SAR GeoTIFF Source: {sar_file}")

    # Step 1: AIS Ingestion (External, Synthetic Validation, Historical GFW, Live Stream, or Mock Fleet)
    if ais_ships is not None:
        print(f"\n[STEP 1] Using {len(ais_ships)} active AIS vessels from external dataset...")
    elif use_validation_cases:
        print("\n[STEP 1] Loading synthetic validation cases as historical AIS data...")
        ais_ships = []
        cases_path = validation_dir or os.path.join(os.path.dirname(__file__), "data", "cases")
        if not os.path.exists(cases_path):
            cases_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "validation_cases"))
        
        target_file = Path(cases_path) / "chennai_2017_ais.json"
        candidate_files = [target_file] if target_file.exists() else list(Path(cases_path).glob("*.json"))

        for file in candidate_files:
            with open(file, "r", encoding="utf-8") as f:
                case_data = json.load(f)
                if isinstance(case_data, list):
                    vessels_by_mmsi = {}
                    for entry in case_data:
                        mmsi = str(entry.get("mmsi", ""))
                        if not mmsi:
                            continue
                        name = entry.get("shipName") or entry.get("name") or f"Vessel-{mmsi[-4:]}"
                        lat = float(entry.get("lat", spill_lat))
                        lon = float(entry.get("lon", spill_lon))
                        ts = entry.get("entryTimestamp") or entry.get("date", "2017-01-28T00:00:00Z")

                        if mmsi not in vessels_by_mmsi:
                            vessels_by_mmsi[mmsi] = {
                                "mmsi": mmsi,
                                "name": name,
                                "imo": str(entry.get("imo", "9000000")),
                                "flag": entry.get("flag", "Unknown"),
                                "vessel_type": entry.get("vesselType") or entry.get("vessel_type") or "Commercial Vessel",
                                "dwt": entry.get("dwt", 50000),
                                "length": entry.get("length", 180.0),
                                "beam": entry.get("beam", 28.0),
                                "lat": lat,
                                "lon": lon,
                                "speed_knots": float(entry.get("speed_knots", 10.0)),
                                "heading": float(entry.get("heading", 0.0)),
                                "track": [],
                            }
                        vessels_by_mmsi[mmsi]["track"].append({
                            "timestamp": ts,
                            "lat": lat,
                            "lon": lon,
                            "speed_knots": float(entry.get("speed_knots", 10.0)),
                            "heading": float(entry.get("heading", 0.0)),
                        })
                        vessels_by_mmsi[mmsi]["lat"] = lat
                        vessels_by_mmsi[mmsi]["lon"] = lon
                    ais_ships.extend(list(vessels_by_mmsi.values()))
                elif isinstance(case_data, dict):
                    ais_ships.extend(case_data.get("ais_ships", []))
        # Skip further historical fetching
    elif use_historical:
        print("\n[STEP 1] Ingesting historical AIS tracks (GFW / Indian incident archive)...")
        hist_kwargs: Dict[str, Any] = dict(
            spill_lat=spill_lat,
            spill_lon=spill_lon,
            radius_km=radius_km,
            api_token=gfw_token,
        )
        if start_date:
            hist_kwargs["start_time"] = f"{start_date}T00:00:00Z"
        if end_date:
            hist_kwargs["end_time"] = f"{end_date}T23:59:59Z"
        ais_ships = fetch_historical_ais(**hist_kwargs)
    elif use_mock:
        print("\n[STEP 1] Ingesting simulated AIS vessel fleet with track histories...")
        ais_ships = fetch_mock_ais(spill_lat, spill_lon, radius_km)
    else:
        print("\n[STEP 1] Ingesting live AIS stream with track accumulation...")
        ais_ships = await fetch_live_ais(
            spill_lat=spill_lat,
            spill_lon=spill_lon,
            radius_km=radius_km,
            listen_seconds=listen_seconds
        )

    # Step 2: SAR Vessel Target Detection (CA-CFAR)
    print("\n[STEP 2] Running 2D CA-CFAR radar detector on SAR scene...")
    sar_ships = detect_sar_ships(
        spill_lat=spill_lat,
        spill_lon=spill_lon,
        ais_ships=ais_ships,
        sar_file=sar_file,
        inject_dark=True
    )

    # Step 3: Correlation, Time Alignment & Dark Vessel Interdiction
    print("\n[STEP 3] Performing spatial-temporal correlation and anomaly scoring...")
    correlate_res = correlate_sar_ais(
        sar_ships=sar_ships,
        ais_ships=ais_ships,
        match_threshold_km=match_threshold_km,
        sar_acquisition_time=sar_time
    )
    if isinstance(correlate_res, tuple):
        matched_ships, dark_ships = correlate_res
        correlated = matched_ships + dark_ships
    else:
        correlated = correlate_res

    # Step 4: GeoJSON Vector Layer Serialization
    print("\n[STEP 4] Serializing results into GeoJSON format...")
    geojson_data = save_geojson(
        correlated=correlated,
        spill_lat=spill_lat,
        spill_lon=spill_lon,
        output_file=output_geojson
    )

    # Step 5: Summary Report
    matched_count = sum(1 for s in correlated if s["status"] == "MATCHED")
    dark_count = sum(1 for s in correlated if s["status"] == "DARK_VESSEL")
    tracks_count = sum(1 for s in correlated if len(s.get("track", [])) >= 2)
    gap_count = sum(len(s.get("behavioral_anomaly", {}).get("gaps_detected", [])) for s in correlated)

    print("\n" + "=" * 65)
    print("  PHASE 4 PIPELINE EXECUTION SUMMARY")
    print("=" * 65)
    print(f"  Total Radar Targets Detected (SAR):  {len(sar_ships)}")
    print(f"  Confirmed Active AIS Vessels:        {len(ais_ships)}")
    print(f"  [MATCHED] Correlated AIS Vessels:    {matched_count}")
    print(f"  [ALERT]   Dark Vessels Intercepted:  {dark_count}")
    print(f"  Vessel Tracks Analyzed:              {tracks_count}")
    print(f"  AIS Blackout Gaps Flagged:           {gap_count}")
    print(f"  GeoJSON Artifact:                    {output_geojson}")
    print("=" * 65)

    return {
        "spill_location": {"lat": spill_lat, "lon": spill_lon},
        "total_sar_targets": len(sar_ships),
        "ais_vessels_found": len(ais_ships),
        "matched_count": matched_count,
        "dark_vessel_count": dark_count,
        "tracks_recorded": tracks_count,
        "gaps_flagged": gap_count,
        "correlated_ships": correlated,
        "geojson": geojson_data,
        "ais_ships": ais_ships,
    }


def main():
    parser = argparse.ArgumentParser(description="SIH26143 Phase 4 AIS & Dark Vessel Pipeline")
    parser.add_argument("--spill-lat", type=float, default=None, help="Incident latitude (overrides --aoi)")
    parser.add_argument("--spill-lon", type=float, default=None, help="Incident longitude (overrides --aoi)")
    parser.add_argument("--radius-km", type=float, default=150.0, help="Search corridor radius in km")
    parser.add_argument("--threshold-km", type=float, default=5.0, help="SAR-to-AIS match distance threshold")
    parser.add_argument("--listen-seconds", type=int, default=10, help="Live stream listen duration")
    parser.add_argument("--mock", action="store_true", help="Force mock AIS data generation with track history")
    parser.add_argument("--historical", action="store_true", help="Use Global Fishing Watch / historical incident archives")
    parser.add_argument("--validation-cases", action="store_true", help="Use synthetic validation cases as historical AIS data")
    parser.add_argument("--aoi", type=str, default=None,
                        choices=["mumbai_high", "chennai_ennore", "gulf_of_kutch", "haldia_sundarbans"],
                        help="Named Indian maritime AOI (sets spill-lat/lon automatically)")
    parser.add_argument("--start-date", type=str, default=None, help="Historical window start date YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=None, help="Historical window end date YYYY-MM-DD")
    parser.add_argument("--sar-file", type=str, default=None, help="Path to real Sentinel-1 GeoTIFF (.tif) file")
    parser.add_argument("--sar-time", type=str, default=None, help="SAR acquisition timestamp for temporal alignment (ISO 8601 UTC)")
    parser.add_argument("--gfw-token", type=str, default=None, help="Global Fishing Watch API token")
    parser.add_argument("--phase3-json", type=str, default=None, help="Path to Phase 3 drift simulation output JSON file")
    parser.add_argument("--output", type=str, default="core/phase4_ais/phase4_output.geojson", help="Output GeoJSON path")

    args = parser.parse_args()

    # Resolve AOI -> lat/lon (--spill-lat/lon override if provided)
    spill_lat = args.spill_lat
    spill_lon = args.spill_lon
    if args.aoi and (spill_lat is None or spill_lon is None):
        aoi_cfg = INDIAN_AOIS.get(args.aoi)
        if aoi_cfg:
            spill_lat = aoi_cfg["lat"]
            spill_lon = aoi_cfg["lon"]
            print(f"[AOI] {aoi_cfg['name']} -> ({spill_lat}, {spill_lon})")
        else:
            print(f"[WARNING] Unknown AOI '{args.aoi}'. Using defaults.")
    if spill_lat is None:
        spill_lat = 18.90
    if spill_lon is None:
        spill_lon = 72.10

    phase3_data = None
    if args.phase3_json and Path(args.phase3_json).exists():
        with open(args.phase3_json, "r", encoding="utf-8") as f:
            phase3_data = json.load(f)

    asyncio.run(run_phase4_pipeline(
        spill_lat=spill_lat,
        spill_lon=spill_lon,
        radius_km=args.radius_km,
        match_threshold_km=args.threshold_km,
        listen_seconds=args.listen_seconds,
        use_mock=args.mock,
        use_historical=args.historical,
        start_date=args.start_date,
        end_date=args.end_date,
        sar_file=args.sar_file,
        sar_time=args.sar_time,
        gfw_token=args.gfw_token,
        phase3_output=phase3_data,
        output_geojson=args.output
    ))


if __name__ == "__main__":
    main()
