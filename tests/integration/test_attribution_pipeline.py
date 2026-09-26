import asyncio
import hashlib
import random
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Ensure project root and backend are on sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import delete, select, text

from app.db.models import (
    AttributionScore,
    AuditLog,
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
from app.db.session import AsyncSessionLocal
from app.services.attribution_pipeline import run_attribution


def test_attribution_pipeline_integration():
    """Run full integration test for Phase 5 DB adapter & pipeline orchestrator."""
    asyncio.run(_async_test_attribution_pipeline())


async def _async_test_attribution_pipeline():
    scene_time = datetime.now(timezone.utc).replace(microsecond=0)
    rand_mmsi = str(random.randint(100_000_000, 999_999_999))
    rand_imo = str(random.randint(1_000_000, 9_999_999))

    vessel_id = None
    scene_id = None
    spill_id = None
    drift_run_id = None

    async with AsyncSessionLocal() as session:
        try:
            # 1. Insert Vessel
            vessel = Vessel(
                mmsi=rand_mmsi,
                imo=rand_imo,
                vessel_name="MV Pipeline Test Tanker",
                vessel_type=VesselTypeEnum.crude_tanker,
                flag_country_code="IN",
                deadweight_tonnage=Decimal("45000.00"),
                source="integration_test",
                metadata_={"test": True},
            )
            session.add(vessel)
            await session.flush()
            vessel_id = vessel.id

            # 2. Insert Scene
            scene = Scene(
                source_provider="CDSE",
                external_scene_id=f"TEST-PIPELINE-{uuid.uuid4().hex[:8].upper()}",
                captured_at=scene_time,
                footprint=text("ST_GeomFromEWKT('SRID=4326;POLYGON((103.7 1.3, 104.2 1.3, 104.2 1.8, 103.7 1.8, 103.7 1.3))')"),
                sha256=hashlib.sha256(b"pipeline_test_scene").hexdigest(),
                processing_status=SceneStatusEnum.processed,
                storage_uri="minio://payodi-scenes/test/pipeline.tif",
                source_metadata={"sensor": "SAR"},
            )
            session.add(scene)
            await session.flush()
            scene_id = scene.id

            # 3. Insert Spill
            spill = Spill(
                scene_id=scene.id,
                spill_polygon=text("ST_GeomFromEWKT('SRID=4326;MULTIPOLYGON(((103.80 1.34, 103.82 1.34, 103.82 1.36, 103.80 1.36, 103.80 1.34)))')"),
                area_sq_km=Decimal("1.500"),
                detection_model_name="OilNetTest",
                detection_model_version="1.0.0",
                confidence_score=Decimal("0.950"),
                status=SpillStatusEnum.confirmed,
            )
            session.add(spill)
            await session.flush()
            spill_id = spill.id

            # 4. Insert 5 Tracks
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
                    speed_knots=Decimal("12.50"),
                    course_degrees=Decimal("45.00"),
                    heading_degrees=Decimal("45.00"),
                    navigational_status="underway",
                    source="integration_test",
                    source_record_id=str(uuid.uuid4()),
                )
                session.add(t)
            await session.flush()

            # 5. Insert DriftRun
            drift_fingerprint = hashlib.sha256(
                f"{scene.id}{vessel.id}{spill.id}{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()

            drift_run = DriftRun(
                scene_id=scene.id,
                vessel_id=vessel.id,
                spill_id=spill.id,
                simulation_version="v1.0.0",
                model_parameters={"wind_drag": 0.03, "diffusion": 0.1},
                run_fingerprint=drift_fingerprint,
                status=DriftStatusEnum.completed,
                output_storage_uri="minio://payodi-scenes/drift/pipeline.json",
                output_sha256=hashlib.sha256(b"drift_output").hexdigest(),
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

            # 6. Call run_attribution
            async with AsyncSessionLocal() as run_session:
                pipeline_res = await run_attribution(
                    session=run_session,
                    drift_run_id=drift_run_id,
                    scoring_version="v1.0.0",
                )

                assert pipeline_res is not None
                assert "verdict" in pipeline_res
                assert pipeline_res["verdict"] in ("prosecutable", "person_of_interest", "insufficient_evidence")

            # 7. Verification queries
            async with AsyncSessionLocal() as verify_session:
                # Assert attribution_scores row exists
                score_stmt = select(AttributionScore).where(AttributionScore.drift_run_id == drift_run_id)
                score_res = await verify_session.execute(score_stmt)
                score_row = score_res.scalar_one_or_none()
                assert score_row is not None, "AttributionScore row was not found!"
                assert score_row.verdict.value in (
                    "prosecutable",
                    "person_of_interest",
                    "insufficient_evidence",
                )

                # Assert cpa_events row exists
                cpa_stmt = select(CpaEvent).where(CpaEvent.drift_run_id == drift_run_id)
                cpa_res = await verify_session.execute(cpa_stmt)
                cpa_row = cpa_res.scalar_one_or_none()
                assert cpa_row is not None, "CpaEvent row was not found!"
                assert cpa_row.min_distance_m >= 0

                # Assert audit_log row exists with 64-char lowercase hex event_hash
                audit_stmt = select(AuditLog).where(
                    AuditLog.entity_type == "attribution_score",
                    AuditLog.entity_id == score_row.id,
                )
                audit_res = await verify_session.execute(audit_stmt)
                audit_row = audit_res.scalar_one_or_none()
                assert audit_row is not None, "AuditLog row was not found!"
                assert re.match(r"^[a-f0-9]{64}$", audit_row.event_hash), (
                    f"event_hash {audit_row.event_hash} is not a 64-character lowercase hex string"
                )

        finally:
            # 8. Cleanup in reverse FK order (skip audit_log — append-only)
            async with AsyncSessionLocal() as cleanup_session:
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
