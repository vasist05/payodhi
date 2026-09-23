"""
Write to drift_runs.

Real DB schema puts most of our flat fields into JSONB columns:
    model_parameters  -> mode, oil_type, release_time, detection_time, engine
    result_summary    -> predicted_lon, predicted_lat, distance_km, forward_score
Plus required columns: scene_id, vessel_id, spill_id, simulation_version,
run_fingerprint (sha256 hex), status.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from .db_config import MOCK_MODE, get_connection, get_mock_path


SIMULATION_VERSION = "phase3_openoil_v1"


def _make_fingerprint(params: dict) -> str:
    s = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(s.encode()).hexdigest()


def _lookup_vessel_id(mmsi: str) -> str:
    """Find the vessel UUID by MMSI. Returns None if not found."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id::text FROM vessels WHERE mmsi = %s", (mmsi,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def write_drift_run(record: dict) -> str:
    """
    record keys:
        spill_id, scene_id, vessel_mmsi (or vessel_id), mode,
        oil_type_sampled, release_time, detection_time,
        predicted_lon, predicted_lat, distance_km, forward_score
    Returns new run id (UUID string).
    """
    # ---- MOCK MODE ----
    if MOCK_MODE:
        row = {
            "run_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        path = get_mock_path("drift_runs")
        try:
            with open(path) as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = []
        existing.append(row)
        with open(path, "w") as f:
            json.dump(existing, f, indent=2, default=str)
        return row["run_id"]

    # ---- REAL DB ----
    # Resolve vessel_id
    vessel_id = record.get("vessel_id")
    if not vessel_id:
        vessel_id = _lookup_vessel_id(record.get("vessel_mmsi", ""))
    if not vessel_id:
        raise ValueError(
            f"vessel not found in DB: mmsi={record.get('vessel_mmsi')}"
        )

    scene_id = record["scene_id"]
    spill_id = record.get("spill_id")

    model_params = {
        "mode": record.get("mode", "forward"),
        "oil_type_sampled": record.get("oil_type_sampled"),
        "release_time": str(record.get("release_time")),
        "detection_time": str(record.get("detection_time")),
        "engine": "OpenOil",
        "engine_version": "1.14",
    }
    result_summary = {
        "predicted_lon": record.get("predicted_lon"),
        "predicted_lat": record.get("predicted_lat"),
        "distance_km": record.get("distance_km"),
        "forward_score": record.get("forward_score"),
    }

    fingerprint = _make_fingerprint({
        **model_params,
        "vessel_id": vessel_id,
        "scene_id": scene_id,
        "spill_id": spill_id,
        "run_nonce": datetime.now(timezone.utc).isoformat(),
    })

    now = datetime.now(timezone.utc)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO drift_runs
                (scene_id, vessel_id, spill_id, simulation_version,
                 model_parameters, run_fingerprint,
                 started_at, completed_at, status, result_summary)
            VALUES
                (%s, %s, %s, %s,
                 %s::jsonb, %s,
                 %s, %s, %s, %s::jsonb)
            RETURNING id::text
            """,
            (
                scene_id,
                vessel_id,
                spill_id,
                SIMULATION_VERSION,
                json.dumps(model_params),
                fingerprint,
                now,
                now,
                "completed",
                json.dumps(result_summary),
            ),
        )
        run_id = cur.fetchone()[0]
        conn.commit()
        return run_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()