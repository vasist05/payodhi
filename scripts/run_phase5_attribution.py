import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import argparse
import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal, engine
from app.db.models import (
    DriftRun,
    Scene,
    Spill,
    Track,
    Vessel,
)
from app.db.models.enums import (
    DriftStatusEnum,
    SceneStatusEnum,
    SpillStatusEnum,
    VesselTypeEnum,
)
from app.services.attribution_pipeline import run_attribution


def parse_args():
    parser = argparse.ArgumentParser(description="Trigger Phase 5 Attribution for a Scene")
    parser.add_argument("--scene-id", type=str, default="f9d8da6d-d5b6-4b53-a060-e116197c8c9e", help="Scene UUID string")
    return parser.parse_args()


async def trigger_attribution_for_scene(scene_id_str: str):
    scene_id = uuid.UUID(scene_id_str)

    async with AsyncSessionLocal() as session:
        # 1. Fetch Scene
        scene = await session.get(Scene, scene_id)
        if not scene:
            raise ValueError(f"Scene {scene_id} not found in database")

        scene_time = scene.captured_at
        if scene_time.tzinfo is None:
            scene_time = scene_time.replace(tzinfo=timezone.utc)

        # 2. Ensure Spill exists
        spill_stmt = select(Spill).where(Spill.scene_id == scene_id).limit(1)
        spill = await session.scalar(spill_stmt)
        if not spill:
            spill = Spill(
                scene_id=scene_id,
                spill_polygon=text("ST_GeomFromEWKT('SRID=4326;MULTIPOLYGON(((80.34 13.24, 80.36 13.24, 80.36 13.26, 80.34 13.26, 80.34 13.24)))')"),
                area_sq_km=Decimal("2.450"),
                detection_model_name="OilNet",
                detection_model_version="1.2.0",
                confidence_score=Decimal("0.920"),
                status=SpillStatusEnum.confirmed,
            )
            session.add(spill)
            await session.flush()

        # 3. Ensure Suspect Vessel exists (MT DAWN KANCHIPURAM)
        vessel_stmt = select(Vessel).where(Vessel.mmsi == "419000988").limit(1)
        vessel = await session.scalar(vessel_stmt)
        if not vessel:
            vessel = Vessel(
                mmsi="419000988",
                imo="9110913",
                vessel_name="MT DAWN KANCHIPURAM",
                vessel_type=VesselTypeEnum.crude_tanker,
                flag_country_code="IN",
                deadweight_tonnage=Decimal("114000.00"),
                source="chennai_2017_historical",
                metadata_={"incident": "chennai_2017"},
            )
            session.add(vessel)
            await session.flush()

        # 4. Ensure Tracks exist
        track_stmt = select(Track).where(Track.vessel_id == vessel.id).limit(1)
        has_track = await session.scalar(track_stmt)
        if not has_track:
            # Trajectory passing through collision zone
            track_points = [
                (80.345, 13.265, scene_time - timedelta(hours=2), Decimal("12.80")),
                (80.348, 13.255, scene_time - timedelta(hours=1), Decimal("12.20")),
                (80.350, 13.250, scene_time - timedelta(minutes=30), Decimal("3.80")),
                (80.352, 13.245, scene_time, Decimal("11.40")),
                (80.355, 13.235, scene_time + timedelta(hours=1), Decimal("11.80")),
            ]
            for lon, lat, t_pt, spd in track_points:
                t = Track(
                    vessel_id=vessel.id,
                    recorded_at=t_pt,
                    position=text(f"ST_GeomFromEWKT('SRID=4326;POINT({lon} {lat})')"),
                    speed_knots=spd,
                    course_degrees=Decimal("215.00"),
                    heading_degrees=Decimal("215.00"),
                    navigational_status="underway",
                    source="chennai_2017_ais",
                    source_record_id=str(uuid.uuid4()),
                )
                session.add(t)
            await session.flush()

        # 5. Ensure DriftRun exists
        drift_stmt = select(DriftRun).where(DriftRun.scene_id == scene_id, DriftRun.vessel_id == vessel.id).limit(1)
        drift_run = await session.scalar(drift_stmt)
        if not drift_run:
            fingerprint = hashlib.sha256(
                f"{scene.id}{vessel.id}{spill.id}{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()
            drift_run = DriftRun(
                scene_id=scene.id,
                vessel_id=vessel.id,
                spill_id=spill.id,
                simulation_version="v1.0.0",
                model_parameters={"wind_drag": 0.03, "diffusion": 0.1},
                run_fingerprint=fingerprint,
                status=DriftStatusEnum.completed,
                output_storage_uri="minio://payodi-scenes/drift/chennai_2017.json",
                output_sha256=hashlib.sha256(b"drift_output_chennai").hexdigest(),
                result_summary={
                    "particle_geometries": [
                        {
                            "lat": 13.255,
                            "lon": 80.348,
                            "time": (scene_time - timedelta(hours=1)).isoformat(),
                        },
                        {
                            "lat": 13.250,
                            "lon": 80.350,
                            "time": scene_time.isoformat(),
                        },
                        {
                            "lat": 13.245,
                            "lon": 80.352,
                            "time": (scene_time + timedelta(hours=1)).isoformat(),
                        },
                    ]
                },
            )
            session.add(drift_run)
            await session.flush()

        await session.commit()
        drift_run_id = drift_run.id

    # 6. Run Attribution Pipeline
    async with AsyncSessionLocal() as session:
        result = await run_attribution(
            session=session,
            drift_run_id=drift_run_id,
            scoring_version="v1.0.0",
        )

    await engine.dispose()
    return result


if __name__ == "__main__":
    args = parse_args()
    verdict = asyncio.run(trigger_attribution_for_scene(args.scene_id))
    # Print JSON verdict
    # Convert any UUIDs to string for JSON serialization
    def serialize_val(v):
        if isinstance(v, uuid.UUID):
            return str(v)
        return v
    cleaned_verdict = {k: serialize_val(v) for k, v in verdict.items()}
    print(json.dumps(cleaned_verdict, indent=2))
