import asyncio
import hashlib
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Ensure project root and backend are on sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.models import (
    AttributionScore,
    CpaEvent,
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
from app.db.session import get_session
from app.main import app

# Use NullPool for tests to prevent connection sharing across different async loops in TestClient
test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_session():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_session] = override_get_session


def test_attribution_api_endpoints():
    """Integration test verifying all Phase 5 attribution API router endpoints via TestClient."""
    scene_time = datetime.now(timezone.utc).replace(microsecond=0)
    rand_mmsi = str(random.randint(100_000_000, 999_999_999))
    rand_imo = str(random.randint(1_000_000, 9_999_999))

    vessel_id = None
    scene_id = None
    spill_id = None
    drift_run_id = None

    # 1. Setup: Insert fake scene, spill, vessel, 5 tracks, drift_run
    async def setup_data():
        nonlocal vessel_id, scene_id, spill_id, drift_run_id
        async with TestSessionLocal() as session:
            vessel = Vessel(
                mmsi=rand_mmsi,
                imo=rand_imo,
                vessel_name="MV API Router Test Tanker",
                vessel_type=VesselTypeEnum.crude_tanker,
                flag_country_code="IN",
                deadweight_tonnage=Decimal("50000.00"),
                source="api_integration_test",
                metadata_={"test": True},
            )
            session.add(vessel)
            await session.flush()
            vessel_id = vessel.id

            scene = Scene(
                source_provider="CDSE",
                external_scene_id=f"TEST-API-{uuid.uuid4().hex[:8].upper()}",
                captured_at=scene_time,
                footprint=text("ST_GeomFromEWKT('SRID=4326;POLYGON((103.7 1.3, 104.2 1.3, 104.2 1.8, 103.7 1.8, 103.7 1.3))')"),
                sha256=hashlib.sha256(b"api_test_scene").hexdigest(),
                processing_status=SceneStatusEnum.processed,
                storage_uri="minio://payodi-scenes/test/api.tif",
                source_metadata={"sensor": "SAR"},
            )
            session.add(scene)
            await session.flush()
            scene_id = scene.id

            spill = Spill(
                scene_id=scene.id,
                spill_polygon=text("ST_GeomFromEWKT('SRID=4326;MULTIPOLYGON(((103.80 1.34, 103.82 1.34, 103.82 1.36, 103.80 1.36, 103.80 1.34)))')"),
                area_sq_km=Decimal("1.800"),
                detection_model_name="OilNetTest",
                detection_model_version="1.0.0",
                confidence_score=Decimal("0.920"),
                status=SpillStatusEnum.confirmed,
            )
            session.add(spill)
            await session.flush()
            spill_id = spill.id

            track_points = [
                (103.79, 1.33, scene_time - timedelta(hours=2)),
                (103.80, 1.34, scene_time - timedelta(hours=1)),
                (103.81, 1.35, scene_time),
                (103.82, 1.36, scene_time + timedelta(hours=1)),
                (103.83, 1.37, scene_time + timedelta(hours=2)),
            ]
            for lon, lat, t_pt in track_points:
                t = Track(
                    vessel_id=vessel.id,
                    recorded_at=t_pt,
                    position=text(f"ST_GeomFromEWKT('SRID=4326;POINT({lon} {lat})')"),
                    speed_knots=Decimal("12.00"),
                    course_degrees=Decimal("45.00"),
                    heading_degrees=Decimal("45.00"),
                    navigational_status="underway",
                    source="api_integration_test",
                    source_record_id=str(uuid.uuid4()),
                )
                session.add(t)
            await session.flush()

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
                output_storage_uri="minio://payodi-scenes/drift/api.json",
                output_sha256=hashlib.sha256(b"drift_api_output").hexdigest(),
                result_summary={
                    "particle_geometries": [
                        {
                            "lat": 1.339,
                            "lon": 103.799,
                            "time": (scene_time - timedelta(hours=1)).isoformat(),
                        },
                        {
                            "lat": 1.350,
                            "lon": 103.810,
                            "time": scene_time.isoformat(),
                        },
                        {
                            "lat": 1.361,
                            "lon": 103.821,
                            "time": (scene_time + timedelta(hours=1)).isoformat(),
                        },
                    ]
                },
            )
            session.add(drift_run)
            await session.commit()
            drift_run_id = drift_run.id

    asyncio.run(setup_data())

    try:
        with TestClient(app) as client:
            # 1. POST /api/v1/attribution/run/{drift_run_id} → status 200, response has 'verdict' and 'total_score'
            run_res = client.post(
                f"/api/v1/attribution/run/{drift_run_id}",
                json={"scoring_version": "v1.0.0"},
            )
            assert run_res.status_code == 200, f"Run failed: {run_res.text}"
            run_data = run_res.json()
            assert "verdict" in run_data, "verdict missing in run response"
            assert "total_score" in run_data, "total_score missing in run response"

            # 2. GET /api/v1/attribution/{drift_run_id} → status 200, verify id, drift_run_id, verdict, total_score keys present
            latest_res = client.get(f"/api/v1/attribution/{drift_run_id}")
            assert latest_res.status_code == 200, f"Get latest failed: {latest_res.text}"
            latest_data = latest_res.json()
            assert "id" in latest_data
            assert "drift_run_id" in latest_data
            assert "verdict" in latest_data
            assert "total_score" in latest_data

            # 3. GET /api/v1/attribution/{drift_run_id}/history → status 200, len >= 1
            history_res = client.get(f"/api/v1/attribution/{drift_run_id}/history")
            assert history_res.status_code == 200, f"Get history failed: {history_res.text}"
            history_data = history_res.json()
            assert isinstance(history_data, list)
            assert len(history_data) >= 1

            # 4. GET /api/v1/attribution/{drift_run_id}/cpa-events → status 200, list
            cpa_res = client.get(f"/api/v1/attribution/{drift_run_id}/cpa-events")
            assert cpa_res.status_code == 200, f"Get CPA events failed: {cpa_res.text}"
            cpa_data = cpa_res.json()
            assert isinstance(cpa_data, list)
            assert len(cpa_data) >= 1
            assert "vessel_position_at_cpa" in cpa_data[0]
            assert "slick_position_at_cpa" in cpa_data[0]

            # 5. POST with random UUID (not in DB) → status 404
            random_uuid = uuid.uuid4()
            not_found_res = client.post(
                f"/api/v1/attribution/run/{random_uuid}",
                json={"scoring_version": "v1.0.0"},
            )
            assert not_found_res.status_code == 404

            # 6. Invalid scoring_version → still 200 (accepts any string)
            custom_version_res = client.post(
                f"/api/v1/attribution/run/{drift_run_id}",
                json={"scoring_version": "custom-version-xyz-999"},
            )
            assert custom_version_res.status_code == 200
            assert "verdict" in custom_version_res.json()

    finally:
        # Cleanup in reverse FK order: cpa_events, attribution_scores, drift_runs, spills, tracks, scenes, vessels. Skip audit_log.
        async def cleanup_data():
            async with TestSessionLocal() as cleanup_session:
                if drift_run_id:
                    await cleanup_session.execute(delete(CpaEvent).where(CpaEvent.drift_run_id == drift_run_id))
                    await cleanup_session.execute(delete(AttributionScore).where(AttributionScore.drift_run_id == drift_run_id))
                    await cleanup_session.execute(delete(DriftRun).where(DriftRun.id == drift_run_id))
                if spill_id:
                    await cleanup_session.execute(delete(Spill).where(Spill.id == spill_id))
                if scene_id:
                    await cleanup_session.execute(delete(Scene).where(Scene.id == scene_id))
                if vessel_id:
                    await cleanup_session.execute(delete(Track).where(Track.vessel_id == vessel_id))
                    await cleanup_session.execute(delete(Vessel).where(Vessel.id == vessel_id))
                await cleanup_session.commit()
            await test_engine.dispose()

        asyncio.run(cleanup_data())
