import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import argparse
import asyncio
import csv
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import VesselTypeEnum
from app.db.models.track import Track
from app.db.models.vessel import Vessel
from app.db.session import AsyncSessionLocal, engine
from app.services.ais_correlation_service import persist_phase4_correlations
from core.phase4_ais.pipeline import run_phase4_pipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Run Phase 4 Pipeline and persist correlations to database")
    parser.add_argument("--spill-lat", type=float, default=13.25, help="Incident latitude")
    parser.add_argument("--spill-lon", type=float, default=80.35, help="Incident longitude")
    parser.add_argument("--scene-id", type=str, required=True, help="Scene UUID string")
    parser.add_argument("--mock", action="store_true", help="Force mock AIS data generation")
    parser.add_argument("--validation-cases", action="store_true", help="Load cached validation AIS data")
    parser.add_argument("--case", type=str, default=None, help="Specific validation case (e.g. chennai_2017)")
    parser.add_argument("--listen-seconds", type=int, default=30, help="Live stream listen duration in seconds")
    parser.add_argument("--radius-km", type=float, default=150.0, help="Search corridor radius in km")
    # CSV additions
    parser.add_argument("--ais-csv", type=str, default=None, help="Path to AIS CSV file")
    parser.add_argument("--ais-csv-limit", type=int, default=30000, help="Cap kept rows AFTER filters")
    parser.add_argument("--ais-csv-window-hours", type=int, default=6, help="Hours before/after sar_time")
    parser.add_argument("--sar-time", type=str, default=None, help="SAR acquisition time ISO8601 UTC")
    parser.add_argument("--output", type=str, default="core/phase4_ais/phase4_output.geojson", help="Output GeoJSON path")

    args = parser.parse_args()
    if args.ais_csv and not args.sar_time:
        parser.error("--sar-time is required when --ais-csv is used")
    return args


async def load_and_persist_ais_csv(
    csv_path: str,
    sar_time_str: str,
    window_hours: int,
    limit: int,
    session: AsyncSession,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    clean_sar_time = sar_time_str.replace("Z", "+00:00")
    sar_dt = datetime.fromisoformat(clean_sar_time)
    if sar_dt.tzinfo is None:
        sar_dt = sar_dt.replace(tzinfo=timezone.utc)

    window_delta = timedelta(hours=window_hours)
    window_min = sar_dt - window_delta
    window_max = sar_dt + window_delta

    rows_read = 0
    skipped_empty = 0
    skipped_mmsi = 0
    skipped_coords = 0
    skipped_bbox = 0
    skipped_utc = 0
    skipped_outside_window = 0

    kept_rows = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_read += 1
            m_raw = row.get("MMSI")
            lon_raw = row.get("LON")
            lat_raw = row.get("LAT")
            utc_raw = row.get("UTC")

            # 1. Skip if MMSI, LON, LAT, UTC empty
            if (
                not m_raw
                or not lon_raw
                or not lat_raw
                or not utc_raw
                or not m_raw.strip()
                or not lon_raw.strip()
                or not lat_raw.strip()
                or not utc_raw.strip()
            ):
                skipped_empty += 1
                continue

            # 2. Skip if MMSI not int or outside 100000000..999999999
            try:
                mmsi_int = int(m_raw)
                if not (100000000 <= mmsi_int <= 999999999):
                    skipped_mmsi += 1
                    continue
            except (ValueError, TypeError):
                skipped_mmsi += 1
                continue

            # 3. Skip if LON outside -180..180, LAT outside -90..90
            try:
                lon = float(lon_raw)
                lat = float(lat_raw)
                if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                    skipped_coords += 1
                    continue
            except (ValueError, TypeError):
                skipped_coords += 1
                continue

            # 4. Skip if outside bbox: LON 24.6-25.2, LAT 37.0-37.6
            if not (24.6 <= lon <= 25.2 and 37.0 <= lat <= 37.6):
                skipped_bbox += 1
                continue

            # 5. Parse UTC (replace 'Z' with '+00:00')
            try:
                u_str = utc_raw.replace("Z", "+00:00")
                utc_dt = datetime.fromisoformat(u_str)
                if utc_dt.tzinfo is None:
                    utc_dt = utc_dt.replace(tzinfo=timezone.utc)
            except Exception:
                skipped_utc += 1
                continue

            # 6. Skip if UTC < sar_time - window_hours
            if utc_dt < window_min:
                skipped_outside_window += 1
                continue

            # 7. If UTC > sar_time + window_hours -> BREAK (CSV is chronological)
            if utc_dt > window_max:
                break

            # Parse optional fields with bounds checking
            try:
                sog = float(row.get("SOG") or 0.0)
            except (ValueError, TypeError):
                sog = 0.0
            sog = min(max(sog, 0.0), 100.0)

            try:
                cog = float(row.get("COG") or 0.0)
            except (ValueError, TypeError):
                cog = 0.0
            cog = min(max(cog, 0.0), 360.0)

            heading_val = row.get("HEADING")
            heading = None
            if heading_val is not None and str(heading_val).strip() != "":
                try:
                    h = float(heading_val)
                    if 0.0 <= h <= 360.0:
                        heading = h
                except (ValueError, TypeError):
                    heading = None

            status_desc = row.get("STATUS_DESC") or None

            # 8. Keep row, count it
            kept_rows.append({
                "mmsi": mmsi_int,
                "utc_dt": utc_dt,
                "utc_raw": utc_raw,
                "lon": lon,
                "lat": lat,
                "sog": sog,
                "cog": cog,
                "heading": heading,
                "status_desc": status_desc,
            })

            # Progress logging: every 5000 rows kept
            if len(kept_rows) % 5000 == 0:
                print(f"loaded {len(kept_rows)} rows (MMSI: {mmsi_int}, UTC: {utc_raw})")

            # 9. Stop after N kept rows = --ais-csv-limit
            if len(kept_rows) >= limit:
                break

    bbox_desc = "LON 24.6-25.2, LAT 37.0-37.6"
    if len(kept_rows) == 0:
        raise ValueError(f"No AIS rows in window {sar_time_str} ± {window_hours}h for bbox {bbox_desc}")

    # Storage: Dedupe MMSIs in batch
    unique_mmsis = set(r["mmsi"] for r in kept_rows)
    vessel_id_map = {}
    new_vessels = 0
    existing_vessels = 0

    for mmsi in sorted(unique_mmsis):
        mmsi_str = str(mmsi)
        stmt = select(Vessel.id).where(Vessel.mmsi == mmsi_str).limit(1)
        existing_id = await session.scalar(stmt)
        if existing_id is not None:
            vessel_id_map[mmsi] = existing_id
            existing_vessels += 1
        else:
            insert_stmt = (
                insert(Vessel)
                .values(
                    mmsi=mmsi_str,
                    vessel_name="UNKNOWN",
                    vessel_type=VesselTypeEnum.unknown,
                    source="aegean_csv",
                )
                .returning(Vessel.id)
            )
            new_id = await session.scalar(insert_stmt)
            vessel_id_map[mmsi] = new_id
            new_vessels += 1

    await session.flush()

    # Build track rows
    track_rows = []
    for r in kept_rows:
        v_id = vessel_id_map[r["mmsi"]]
        track_rows.append({
            "vessel_id": v_id,
            "recorded_at": r["utc_dt"],
            "position": func.ST_SetSRID(func.ST_MakePoint(r["lon"], r["lat"]), 4326),
            "speed_knots": r["sog"],
            "course_degrees": r["cog"],
            "heading_degrees": r["heading"],
            "navigational_status": r["status_desc"],
            "source": "aegean_csv",
            "source_record_id": f"{r['mmsi']}:{r['utc_raw']}",
        })

    # Bulk insert tracks in 1000-row batches with ON CONFLICT DO NOTHING
    tracks_inserted = 0
    for i in range(0, len(track_rows), 1000):
        batch = track_rows[i : i + 1000]
        ins_tracks = insert(Track).values(batch).on_conflict_do_nothing()
        res = await session.execute(ins_tracks)
        tracks_inserted += (res.rowcount if res.rowcount and res.rowcount > 0 else 0)

    await session.commit()

    # Build ais_ships for run_phase4_pipeline
    vessels_dict = {}
    for r in kept_rows:
        m = str(r["mmsi"])
        if m not in vessels_dict:
            vessels_dict[m] = {
                "mmsi": m,
                "name": f"Vessel-{m[-4:]}",
                "imo": "9000000",
                "flag": "Unknown",
                "vessel_type": r.get("status_desc") or "Commercial Vessel",
                "dwt": 50000,
                "length": 180.0,
                "beam": 28.0,
                "lat": r["lat"],
                "lon": r["lon"],
                "speed_knots": r["sog"],
                "heading": r["heading"] if r["heading"] is not None else 0.0,
                "track": [],
            }
        vessels_dict[m]["lat"] = r["lat"]
        vessels_dict[m]["lon"] = r["lon"]
        vessels_dict[m]["speed_knots"] = r["sog"]
        vessels_dict[m]["heading"] = r["heading"] if r["heading"] is not None else 0.0
        vessels_dict[m]["track"].append({
            "timestamp": r["utc_raw"],
            "lat": r["lat"],
            "lon": r["lon"],
            "speed_knots": r["sog"],
            "heading": r["heading"] if r["heading"] is not None else 0.0,
        })

    ais_ships = list(vessels_dict.values())

    metrics = {
        "rows_read": rows_read,
        "skipped_empty": skipped_empty,
        "skipped_mmsi": skipped_mmsi,
        "skipped_coords": skipped_coords,
        "skipped_bbox": skipped_bbox,
        "skipped_utc": skipped_utc,
        "skipped_outside_window": skipped_outside_window,
        "total_skipped": (
            skipped_empty
            + skipped_mmsi
            + skipped_coords
            + skipped_bbox
            + skipped_utc
            + skipped_outside_window
        ),
        "rows_kept": len(kept_rows),
        "unique_vessels_total": len(unique_mmsis),
        "new_vessels": new_vessels,
        "existing_vessels": existing_vessels,
        "tracks_inserted": tracks_inserted,
    }

    return metrics, ais_ships


async def persist_live_ais_ships(
    ais_ships: List[Dict[str, Any]], session: AsyncSession, source: str = "aisstream"
):
    if not ais_ships:
        return
    for ship in ais_ships:
        raw_mmsi = str(ship.get("mmsi", "")).strip()
        if not raw_mmsi:
            continue
        if raw_mmsi.isdigit() and len(raw_mmsi) <= 9:
            mmsi_str = raw_mmsi.zfill(9)
        elif raw_mmsi.isdigit() and len(raw_mmsi) == 9:
            mmsi_str = raw_mmsi
        else:
            mmsi_str = None

        vessel_id = None
        if mmsi_str:
            stmt = select(Vessel.id).where(Vessel.mmsi == mmsi_str).limit(1)
            vessel_id = await session.scalar(stmt)

        if not vessel_id:
            v_name = ship.get("name") or "UNKNOWN"
            insert_v = (
                insert(Vessel)
                .values(
                    mmsi=mmsi_str,
                    vessel_name=v_name,
                    vessel_type=VesselTypeEnum.unknown,
                    source=source,
                )
                .returning(Vessel.id)
            )
            vessel_id = await session.scalar(insert_v)

        track_rows = []
        for wp in ship.get("track", []):
            try:
                t_str = wp.get("timestamp", "").replace("Z", "+00:00")
                t_dt = datetime.fromisoformat(t_str) if t_str else datetime.now(timezone.utc)
                if t_dt.tzinfo is None:
                    t_dt = t_dt.replace(tzinfo=timezone.utc)
            except Exception:
                t_dt = datetime.now(timezone.utc)

            sog = min(max(float(wp.get("speed_knots") or 0.0), 0.0), 100.0)
            hdg = wp.get("heading")
            heading_deg = None
            if hdg is not None:
                try:
                    h_val = float(hdg)
                    if 0.0 <= h_val <= 360.0:
                        heading_deg = h_val
                except Exception:
                    pass
            cog = heading_deg if heading_deg is not None else 0.0

            lon = float(wp.get("lon", 0.0))
            lat = float(wp.get("lat", 0.0))

            mmsi_rec = mmsi_str or raw_mmsi
            track_rows.append({
                "vessel_id": vessel_id,
                "recorded_at": t_dt,
                "position": func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326),
                "speed_knots": sog,
                "course_degrees": cog,
                "heading_degrees": heading_deg,
                "navigational_status": wp.get("status_desc"),
                "source": source,
                "source_record_id": f"{mmsi_rec}:{wp.get('timestamp', str(t_dt))}",
            })

        if track_rows:
            ins_stmt = insert(Track).values(track_rows).on_conflict_do_nothing()
            await session.execute(ins_stmt)

    await session.commit()


async def _run_all(args):
    metrics = None
    ais_ships = None

    if args.ais_csv:
        async with AsyncSessionLocal() as session:
            metrics, ais_ships = await load_and_persist_ais_csv(
                csv_path=args.ais_csv,
                sar_time_str=args.sar_time,
                window_hours=args.ais_csv_window_hours,
                limit=args.ais_csv_limit,
                session=session,
            )

        phase4_result = await run_phase4_pipeline(
            spill_lat=args.spill_lat,
            spill_lon=args.spill_lon,
            radius_km=args.radius_km,
            sar_time=args.sar_time,
            ais_ships=ais_ships,
            output_geojson=args.output,
        )
    else:
        phase4_result = await run_phase4_pipeline(
            spill_lat=args.spill_lat,
            spill_lon=args.spill_lon,
            radius_km=args.radius_km,
            listen_seconds=args.listen_seconds,
            use_mock=args.mock,
            use_validation_cases=args.validation_cases or (args.case is not None),
            sar_time=args.sar_time,
            output_geojson=args.output,
        )
        source_name = "mock" if args.mock else (f"indian_{args.case or 'benchmark'}" if (args.validation_cases or args.case) else "aisstream")
        ships_to_persist = phase4_result.get("ais_ships", [])
        if ships_to_persist:
            async with AsyncSessionLocal() as session:
                await persist_live_ais_ships(ships_to_persist, session, source=source_name)

    # Persist correlations to DB
    detected_at = None
    if args.sar_time:
        try:
            clean_time = args.sar_time.replace("Z", "+00:00")
            detected_at = datetime.fromisoformat(clean_time)
            if detected_at.tzinfo is None:
                detected_at = detected_at.replace(tzinfo=timezone.utc)
        except Exception:
            detected_at = None

    async with AsyncSessionLocal() as session:
        persist_result = await persist_phase4_correlations(
            session=session,
            scene_id=UUID(args.scene_id),
            phase4_result=phase4_result,
            detected_at=detected_at,
        )
        await session.commit()

    # Query final DB counts
    async with AsyncSessionLocal() as session:
        r_vessels = await session.execute(text("SELECT COUNT(*) FROM vessels"))
        r_tracks = await session.execute(text("SELECT COUNT(*) FROM tracks"))
        r_sar = await session.execute(text("SELECT COUNT(*) FROM sar_targets"))
        r_corr = await session.execute(text("SELECT COUNT(*) FROM target_correlations"))
        db_counts = {
            "vessels": r_vessels.scalar(),
            "tracks": r_tracks.scalar(),
            "sar_targets": r_sar.scalar(),
            "target_correlations": r_corr.scalar(),
        }

    await engine.dispose()

    return metrics, phase4_result, persist_result, db_counts


if __name__ == "__main__":
    args = parse_args()
    metrics, phase4_result, persist_result, db_counts = asyncio.run(_run_all(args))

    if metrics:
        print("\n" + "=" * 50)
        print("PHASE 4 CSV INGESTION & PIPELINE REPORT")
        print("=" * 50)
        print(f"Rows read from CSV: {metrics['rows_read']}")
        print("Rows skipped (breakdown):")
        print(f"  - Empty fields: {metrics['skipped_empty']}")
        print(f"  - Invalid MMSI: {metrics['skipped_mmsi']}")
        print(f"  - Invalid coordinates: {metrics['skipped_coords']}")
        print(f"  - Outside bbox: {metrics['skipped_bbox']}")
        print(f"  - Invalid UTC: {metrics['skipped_utc']}")
        print(f"  - Outside window: {metrics['skipped_outside_window']}")
        print(f"  - Total skipped: {metrics['total_skipped']}")
        print(f"Rows kept: {metrics['rows_kept']}")
        print(
            f"Unique vessels (new / existing): {metrics['unique_vessels_total']} "
            f"({metrics['new_vessels']} new / {metrics['existing_vessels']} existing)"
        )
        print(f"Tracks inserted: {metrics['tracks_inserted']}")
        print(f"CA-CFAR targets: {phase4_result.get('total_sar_targets')}")
        print(f"Matched vessels: {phase4_result.get('matched_count')}")
        print(f"Dark vessels: {phase4_result.get('dark_vessel_count')}")
        print(
            f"Final DB counts: vessels={db_counts['vessels']}, "
            f"tracks={db_counts['tracks']}, "
            f"sar_targets={db_counts['sar_targets']}, "
            f"target_correlations={db_counts['target_correlations']}"
        )
        print("=" * 50)
    else:
        print("PHASE 4 RESULT KEYS:", list(phase4_result.keys()))
        print("PERSIST RESULT:", persist_result)
        print("sar_targets count:", db_counts["sar_targets"])
        print("target_correlations count:", db_counts["target_correlations"])
