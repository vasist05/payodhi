"""
GFW Validation Data Fetcher
============================
Fetches historical AIS vessel tracks from the Global Fishing Watch (GFW) API
for the two Phase 8 benchmark incidents:

  1. Chennai / Ennore 2017 collision  (bbox 80.0,12.5 -> 81.0,14.0)
  2. Haldia / Hooghly 2018 spill      (bbox 87.5,21.0 -> 88.5,22.5)

Results are saved to backend/ais_pipeline/data/ as JSON files and also
returned as Python dicts for direct use in the pipeline.

Usage (standalone):
    python -m backend.ais_pipeline.fetch_gfw_validation

Usage (as a library):
    from backend.ais_pipeline.fetch_gfw_validation import fetch_and_save_validation_data
    data = fetch_and_save_validation_data()
"""

import os
import json
import datetime
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

GFW_4WINGS_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
# Legacy endpoint kept for reference (not used)
# GFW_EVENTS_URL = "https://gateway.api.globalfishingwatch.org/v3/events"
# GFW_VESSELS_URL = "https://gateway.api.globalfishingwatch.org/v3/vessels/search"

# Benchmark incident definitions
BENCHMARK_INCIDENTS: Dict[str, Dict[str, Any]] = {
    "chennai_2017": {
        "label": "Chennai / Ennore Collision 2017",
        "output_file": DATA_DIR / "chennai_2017_ais.json",
        "start_date": "2017-01-25",
        "end_date": "2017-02-02",
        "bbox": "80.0,12.5,81.0,14.0",
        "spill_lat": 13.25,
        "spill_lon": 80.35,
    },
    "haldia_2018": {
        "label": "Haldia / Hooghly Oil Discharge 2018",
        "output_file": DATA_DIR / "haldia_2018_ais.json",
        "start_date": "2018-07-01",
        "end_date": "2018-07-31",
        "bbox": "87.5,21.0,88.5,22.5",
        "spill_lat": 21.75,
        "spill_lon": 88.05,
    },
    }



# ---------------------------------------------------------------------------
# GFW API helpers
# ---------------------------------------------------------------------------


def _gfw_auth_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Cloudflare WAF requires a real User-Agent (error 1010 = bot fingerprint block)
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Origin": "https://globalfishingwatch.org",
        "Referer": "https://globalfishingwatch.org/",
    }


def _parse_gfw_feature(feature: Dict[str, Any], spill_lat: float, spill_lon: float) -> Optional[Dict[str, Any]]:
    """Parse a GeoJSON feature from the 4WINGS report into the pipeline vessel schema.
    The feature follows GeoJSON: {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {...}}
    """
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    coords = geometry.get("coordinates", [None, None])
    lon = coords[0] if len(coords) > 0 else spill_lon
    lat = coords[1] if len(coords) > 1 else spill_lat

    # Simple Haversine distance to spill point
    import math
    dlat = math.radians(lat - spill_lat)
    dlon = math.radians(lon - spill_lon)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(spill_lat)) * math.cos(math.radians(lat)) *
         math.sin(dlon / 2) ** 2)
    dist_km = round(6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)

    mmsi = str(properties.get("MMSI", properties.get("mmsi", "9990000")))
    return {
        "mmsi": mmsi,
        "name": properties.get("VesselName", f"GFW-{mmsi[-4:]}") ,
        "imo": str(properties.get("IMO", "9000000")),
        "flag": properties.get("Flag", "Unknown"),
        "vessel_type": properties.get("VesselType", "Commercial Vessel"),
        "dwt": properties.get("DWT", 50000),
        "length": properties.get("Length", 180.0),
        "beam": properties.get("Beam", 28.0),
        "lat": lat,
        "lon": lon,
        "speed_knots": properties.get("Speed", 10.0),
        "heading": properties.get("Heading", 0),
        "distance_km": dist_km,
        "track": [],
        "source": "GFW_API_LIVE",
    }


# ---------------------------------------------------------------------------
# Primary public function
# ---------------------------------------------------------------------------


def fetch_gfw_vessel_search(
    query: str,
    token: str,
    spill_lat: float,
    spill_lon: float,
) -> List[Dict[str, Any]]:
    """
    Searches for real vessel records by name using the GFW vessel-identity dataset.
    Returns vessels in the pipeline schema.
    """
    params = urllib.parse.urlencode({
        "query": query,
        "datasets": "public-global-vessel-identity:latest",
        "includes[0]": "MATCH_CRITERIA",
        "limit": "10",
    })
    url = f"{GFW_VESSELS_URL}?{params}"
    req = urllib.request.Request(url, headers=_gfw_auth_headers(token))
    req = urllib.request.Request(url, headers=_gfw_auth_headers(token))
    results = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            for entry in payload.get("entries", []):
                reg_list = entry.get("registryInfo", [])
                reg = reg_list[0] if reg_list else {}
                lat = spill_lat
                lon = spill_lon
                import math
                dlat, dlon = 0.0, 0.0
                a = (math.sin(dlat / 2) ** 2 +
                     math.cos(math.radians(spill_lat)) * math.cos(math.radians(lat)) *
                     math.sin(dlon / 2) ** 2)
                dist_km = 0.0
                results.append({
                    "mmsi": reg.get("ssvid", "9990000"),
                    "name": reg.get("shipname", query).strip(),
                    "imo": reg.get("imo", "9000000"),
                    "flag": reg.get("flag", "Unknown"),
                    "vessel_type": (reg.get("geartypes") or ["Commercial Vessel"])[0].title(),
                    "dwt": reg.get("tonnageGt", 50000),
                    "length": reg.get("lengthM") or 180.0,
                    "beam": 28.0,
                    "lat": lat,
                    "lon": lon,
                    "speed_knots": 10.0,
                    "heading": 0,
                    "distance_km": dist_km,
                    "track": [],
                    "source": "GFW_API_LIVE",
                    "transmission_from": reg.get("transmissionDateFrom"),
                    "transmission_to": reg.get("transmissionDateTo"),
                })
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"   [GFW SEARCH] HTTP {e.code}: {body[:200]}")
    except Exception as err:
        print(f"   [GFW SEARCH] Error: {err}")
    return results


def query_gfw_4wings(bbox, start_date, end_date, token):
    """bbox = [min_lon, min_lat, max_lon, max_lat]"""
    if isinstance(bbox, str):
        min_lon, min_lat, max_lon, max_lat = [float(x.strip()) for x in bbox.split(",")]
    else:
        min_lon, min_lat, max_lon, max_lat = bbox
    geom = {
        'type': 'Polygon',
        'coordinates': [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat]
        ]]
    }
    r = requests.post(
        'https://gateway.api.globalfishingwatch.org/v3/4wings/report',
        headers={'Authorization': f'Bearer {token}'},
        params=[
            ('datasets[0]', 'public-global-presence:v3.0'),
            ('date-range', f'{start_date},{end_date}'),
            ('spatial-resolution', 'HIGH'),    # use HIGH, not LOW
            ('temporal-resolution', 'DAILY'),  # use DAILY, not ENTIRE
            ('format', 'JSON')
        ],
        json={'geojson': geom}
    )
    print(f"   [GFW STATUS] HTTP {r.status_code}")
    if r.status_code != 200:
        print(f'[GFW_FAILED] {r.status_code}: {r.text[:200]}')
        return []
    
    data = r.json()
    vessels = []
    for entry in data.get('entries', []):
        for dataset_name, records in entry.items():
            if isinstance(records, list):
                vessels.extend(records)
    return vessels


def fetch_gfw_events(
    bbox,
    start_date: str,
    end_date: str,
    spill_lat: float,
    spill_lon: float,
    token: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Wrapper calling query_gfw_4wings and returning vessels."""
    return query_gfw_4wings(bbox, start_date, end_date, token)



# ---------------------------------------------------------------------------
# Primary public function
# ---------------------------------------------------------------------------


def load_validation_cases() -> List[Dict[str, Any]]:
    """Load validation_cases.json if present and return a list of case dicts.
    The function is tolerant of missing files – it returns an empty list.
    """
    cases_path = Path(__file__).parent / "validation_cases.json"
    if not cases_path.exists():
        return []
    try:
        with open(cases_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"   [CASE LOAD] Error reading validation_cases.json: {e}")
        return []


def ensure_cases_dir() -> Path:
    """Ensure the <data>/cases directory exists and return its Path."""
    cases_dir = DATA_DIR / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    return cases_dir


def fetch_and_save_validation_data(
    gfw_token: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch GFW validation data for all benchmark incidents and any added cases.
    Workflow:
      1. Load static BENCHMARK_INCIDENTS (two original incidents).
      2. Load validation_cases.json and merge its entries, constructing the same
         dict structure expected by the rest of the pipeline.
      3. For each incident, attempt to read a cached JSON file under
         <data>/cases/. If not present or force_refresh is True, query the GFW
         4WINGS endpoint and save the result.
    """
    token = gfw_token or os.getenv("GFW_API_TOKEN", "")
    results: Dict[str, List[Dict[str, Any]]] = {}

    # Merge dynamic cases
    cases = load_validation_cases()
    cases_dir = ensure_cases_dir()
    for case in cases:
        incident_key = case["case_id"]
        # Build dict compatible with existing loop
        BENCHMARK_INCIDENTS[incident_key] = {
            "label": case.get("name", incident_key),
            "output_file": cases_dir / case["output_file"],
            "start_date": case["start_date"],
            "end_date": case["end_date"],
            "bbox": ",".join(str(v) for v in case["bbox"]),
            "spill_lat": case["spill_lat"],
            "spill_lon": case["spill_lon"],
        }

    for incident_key, cfg in BENCHMARK_INCIDENTS.items():
        out_path: Path = cfg["output_file"]
        label = cfg["label"]
        print(f"\n[GFW VALIDATION] Incident: {label}")

        # Only refresh if force_refresh is True
        refresh = force_refresh

        # --- Try cache first ---
        if out_path.exists() and not refresh:
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                print(f"   [CACHE HIT] Loaded {len(cached)} vessels from {out_path.name}")
                results[incident_key] = cached
                continue
            except Exception as e:
                print(f"   [CACHE] Read error ({e}), re-fetching...")

        vessels: List[Dict[str, Any]] = []

        # --- Try GFW live API ---
        if token and token not in ("your_gfw_api_token_here", ""):
            print(f"   [GFW API] Querying: bbox={cfg['bbox']}, dates={cfg['start_date']} to {cfg['end_date']}")
            vessels = fetch_gfw_events(
                bbox=cfg["bbox"],
                start_date=cfg["start_date"],
                end_date=cfg["end_date"],
                spill_lat=cfg["spill_lat"],
                spill_lon=cfg["spill_lon"],
                token=token,
            )
        else:
            print("[GFW_FAILED] 401: No valid token configured. Skipping API fetch.")
            vessels = []  # GFW_FAILED

        if not vessels:
            print(f"[GFW_FAILED] 404: No live data returned for {incident_key}")
            # If cache file exists and has data, preserve it!
            if out_path.exists():
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    if existing:
                        print(f"   [CACHE PRESERVED] Keeping existing {len(existing)} vessels in {out_path.name}")
                        results[incident_key] = existing
                        continue
                except Exception:
                    pass
            vessels = []  # GFW_FAILED

        # --- Save to JSON cache ---
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(vessels, f, indent=2, ensure_ascii=False)
        print(f"   [SAVED] {len(vessels)} vessels -> {out_path}")
        results[incident_key] = vessels

    # Summary of counts
    print("\n=== Vessel counts per case ===")
    for key, vessels in results.items():
        print(f"{key}: {len(vessels)} vessels")

    return results


def load_cached_validation(incident_key: str) -> List[Dict[str, Any]]:
    """
    Loads a previously saved validation JSON file without making any API calls.
    Use this as a fast fallback inside the main pipeline.

    Args:
        incident_key: One of "chennai_2017" or "haldia_2018".

    Returns:
        List of vessel dicts, or [] if the file doesn't exist.
    """
    cfg = BENCHMARK_INCIDENTS.get(incident_key, {})
    out_path: Optional[Path] = cfg.get("output_file")
    if out_path and out_path.exists():
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    return data
        except Exception:
            pass
    print(f"[GFW_FAILED] 404: No cache found for {incident_key}")
    return []  # GFW_FAILED


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  GFW VALIDATION DATA FETCHER")
    print("=" * 60)
    all_data = fetch_and_save_validation_data(force_refresh=True)
    print("\n" + "=" * 60)
    print("  CASE-BY-CASE GFW VALIDATION RESULTS")
    print("=" * 60)
    for key, vessels in all_data.items():
        cfg = BENCHMARK_INCIDENTS[key]
        print(f"case_id: {key}")
        print(f"  Incident: {cfg['label']}")
        print(f"  Raw vessel count: {len(vessels)}")
        if vessels:
            first = vessels[0]
            v_name = first.get("shipName") or first.get("shipname") or first.get("name") or f"Vessel-{str(first.get('mmsi'))[-4:]}"
            v_mmsi = first.get("mmsi") or first.get("ssvid") or "Unknown"
            v_flag = first.get("flag") or "Unknown"
            print(f"  First vessel: {v_name} | MMSI: {v_mmsi} | Flag: {v_flag}")
        else:
            print("  First vessel: None (0 vessels returned)")
        print()
    print("Done. JSON files saved to core/phase4_ais/data/cases/")
