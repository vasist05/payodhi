import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select
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
from app.db.models import MatchStatusEnum, SarTarget, Scene, TargetCorrelation, Vessel
from app.db.models.enums import SceneStatusEnum, VesselTypeEnum
from app.services.ais_correlation_service import persist_phase4_correlations
from core.phase4_ais.pipeline import run_phase4_pipeline

test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


def test_phase4_database_linkage():
    """Integration test verifying Phase 4 pipeline outputs are saved cleanly into PostgreSQL."""
    asyncio.run(_async_test_phase4_database_linkage())


async def _async_test_phase4_database_linkage():
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    rand_suffix = uuid.uuid4().hex[:8]

    # 1. Execute Phase 4 pipeline (mock fleet)
    phase4_result = await run_phase4_pipeline(
        spill_lat=18.90,
        spill_lon=72.10,
        radius_km=30.0,
        match_threshold_km=5.0,
        use_mock=True,
    )
    assert phase4_result["total_sar_targets"] > 0
    assert len(phase4_result["correlated_ships"]) > 0

    scene_id = None
    vessel_id = None
    saved_target_ids = []
    saved_correlation_ids = []

    async with TestSessionLocal() as session:
        try:
            # 2. Insert test scene
            scene = Scene(
                source_provider="sentinel1",
                external_scene_id=f"SCENE_PHASE4_LINK_{rand_suffix}",
                captured_at=now_utc,
                footprint=WKTElement("POLYGON((71.5 18.5, 72.5 18.5, 72.5 19.5, 71.5 19.5, 71.5 18.5))", srid=4326),
                storage_uri=f"s3://scenes/phase4_{rand_suffix}.safe",
                sha256="b" * 64,
                processing_status=SceneStatusEnum.processed,
                source_metadata={},
            )
            session.add(scene)

            # Insert one of the mock fleet vessels so that matched correlation can link to it
            # Mock vessel MMSI in pipeline is '419000456' (SAGAR KANYA)
            vessel = Vessel(
                mmsi="419000456",
                vessel_name="SAGAR KANYA",
                vessel_type=VesselTypeEnum.cargo,
                source="ais",
            )
            session.add(vessel)
            await session.commit()

            scene_id = scene.id
            vessel_id = vessel.id

            # 3. Call persist_phase4_correlations
            res = await persist_phase4_correlations(
                session=session,
                scene_id=scene_id,
                phase4_result=phase4_result,
                detected_at=now_utc,
            )
            await session.commit()

            saved_target_ids = res["sar_target_ids"]
            saved_correlation_ids = res["correlation_ids"]

            assert res["saved_targets_count"] == len(phase4_result["correlated_ships"])
            assert res["saved_correlations_count"] == len(phase4_result["correlated_ships"])

            # 4. Verify in DB
            targets = (await session.scalars(
                select(SarTarget).where(SarTarget.scene_id == scene_id)
            )).all()
            assert len(targets) == res["saved_targets_count"]

            correlations = (await session.scalars(
                select(TargetCorrelation).where(TargetCorrelation.id.in_(saved_correlation_ids))
            )).all()
            assert len(correlations) == res["saved_correlations_count"]

            # Verify that at least one is dark_vessel and has vessel_id IS NULL
            dark_corrs = [c for c in correlations if c.match_status == MatchStatusEnum.dark_vessel]
            assert len(dark_corrs) >= 1
            for dc in dark_corrs:
                assert dc.vessel_id is None

            # Verify that at least one is matched and has vessel_id == vessel_id
            matched_corrs = [c for c in correlations if c.match_status == MatchStatusEnum.matched]
            assert len(matched_corrs) >= 1
            assert any(mc.vessel_id == vessel_id for mc in matched_corrs)

        finally:
            # 5. Cleanup
            if saved_correlation_ids:
                await session.execute(delete(TargetCorrelation).where(TargetCorrelation.id.in_(saved_correlation_ids)))
            if saved_target_ids:
                await session.execute(delete(SarTarget).where(SarTarget.id.in_(saved_target_ids)))
            if vessel_id:
                await session.execute(delete(Vessel).where(Vessel.id == vessel_id))
            if scene_id:
                await session.execute(delete(Scene).where(Scene.id == scene_id))
            await session.commit()
