import asyncio
import random
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
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
    MatchStatusEnum,
    SarTarget,
    Scene,
    TargetCorrelation,
    Vessel,
)
from app.db.models.enums import SceneStatusEnum, VesselTypeEnum

test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


def test_phase4_tables_crud_and_constraints():
    """Integration test verifying Phase 4 tables (sar_targets, target_correlations)
    and their foreign key, check, and unique constraints.
    """
    asyncio.run(_async_test_phase4_tables_crud_and_constraints())


async def _async_test_phase4_tables_crud_and_constraints():
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    rand_suffix = uuid.uuid4().hex[:8]

    created_scene_ids = []
    created_vessel_ids = []
    created_sar_target_ids = []
    created_correlation_ids = []

    async with TestSessionLocal() as session:
        try:
            # 1. Insert scene
            scene = Scene(
                source_provider="sentinel1",
                external_scene_id=f"TEST_PHASE4_SCENE_{rand_suffix}",
                captured_at=now_utc,
                footprint=WKTElement("POLYGON((80.0 10.0, 81.0 10.0, 81.0 11.0, 80.0 11.0, 80.0 10.0))", srid=4326),
                storage_uri=f"s3://scenes/test_{rand_suffix}.safe",
                sha256="a" * 64,
                processing_status=SceneStatusEnum.processed,
                source_metadata={},
            )
            session.add(scene)
            await session.commit()
            scene_id = scene.id
            created_scene_ids.append(scene_id)
            assert scene_id is not None

            # Helper vessel for matched correlations
            vessel = Vessel(
                mmsi=str(random.randint(100_000_000, 999_999_999)),
                imo=str(random.randint(1_000_000, 9_999_999)),
                vessel_name=f"TEST VESSEL {rand_suffix}",
                vessel_type=VesselTypeEnum.cargo,
                source="ais",
            )
            session.add(vessel)
            await session.commit()
            vessel_id = vessel.id
            created_vessel_ids.append(vessel_id)

            # 2. Insert sar_target linked to scene -> success
            sar_target_1 = SarTarget(
                scene_id=scene_id,
                detected_at=now_utc,
                position=WKTElement("POINT(80.5 10.5)", srid=4326),
                intensity=Decimal("12.50"),
                confidence=Decimal("0.850"),
                patch_uri=f"s3://patches/target_1_{rand_suffix}.png",
                source="sentinel-1_cfar",
            )
            session.add(sar_target_1)
            await session.commit()
            sar_target_1_id = sar_target_1.id
            created_sar_target_ids.append(sar_target_1_id)
            assert sar_target_1_id is not None

            # 3. Insert target_correlation with match_status='matched' + vessel_id set -> success
            corr_1 = TargetCorrelation(
                sar_target_id=sar_target_1_id,
                vessel_id=vessel_id,
                match_status=MatchStatusEnum.matched,
                haversine_distance_m=Decimal("120.50"),
                anomaly_flags={"speed_anomaly": False},
            )
            session.add(corr_1)
            await session.commit()
            corr_1_id = corr_1.id
            created_correlation_ids.append(corr_1_id)
            assert corr_1_id is not None

            # 4. Insert target_correlation with match_status='dark_vessel' + vessel_id NULL -> success
            sar_target_2 = SarTarget(
                scene_id=scene_id,
                detected_at=now_utc,
                position=WKTElement("POINT(80.6 10.6)", srid=4326),
                intensity=Decimal("18.00"),
                confidence=Decimal("0.920"),
                patch_uri=f"s3://patches/target_2_{rand_suffix}.png",
                source="sentinel-1_cfar",
            )
            session.add(sar_target_2)
            await session.commit()
            sar_target_2_id = sar_target_2.id
            created_sar_target_ids.append(sar_target_2_id)

            corr_2 = TargetCorrelation(
                sar_target_id=sar_target_2_id,
                vessel_id=None,
                match_status=MatchStatusEnum.dark_vessel,
                haversine_distance_m=None,
                anomaly_flags={"ais_transponder_off": True},
            )
            session.add(corr_2)
            await session.commit()
            corr_2_id = corr_2.id
            created_correlation_ids.append(corr_2_id)
            assert corr_2_id is not None

            # 5. Insert sar_target with confidence=1.5 -> IntegrityError
            sar_target_invalid_conf = SarTarget(
                scene_id=scene_id,
                detected_at=now_utc,
                position=WKTElement("POINT(80.7 10.7)", srid=4326),
                confidence=Decimal("1.500"),
                source="sentinel-1_cfar",
            )
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(sar_target_invalid_conf)
                    await session.flush()

            # Prepare another sar_target for negative correlation tests
            sar_target_3 = SarTarget(
                scene_id=scene_id,
                detected_at=now_utc,
                position=WKTElement("POINT(80.8 10.8)", srid=4326),
                confidence=Decimal("0.750"),
                source="sentinel-1_cfar",
            )
            session.add(sar_target_3)
            await session.commit()
            sar_target_3_id = sar_target_3.id
            created_sar_target_ids.append(sar_target_3_id)

            # 6. Insert target_correlation match_status='dark_vessel' + vessel_id set -> IntegrityError (CHECK)
            corr_invalid_dark = TargetCorrelation(
                sar_target_id=sar_target_3_id,
                vessel_id=vessel_id,
                match_status=MatchStatusEnum.dark_vessel,
            )
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(corr_invalid_dark)
                    await session.flush()

            # 7. Insert target_correlation match_status='matched' + vessel_id NULL -> IntegrityError (CHECK)
            corr_invalid_matched = TargetCorrelation(
                sar_target_id=sar_target_3_id,
                vessel_id=None,
                match_status=MatchStatusEnum.matched,
            )
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(corr_invalid_matched)
                    await session.flush()

            # 8. Insert second target_correlation for same sar_target -> IntegrityError (UNIQUE)
            corr_duplicate_sar = TargetCorrelation(
                sar_target_id=sar_target_1_id,  # already has corr_1
                vessel_id=vessel_id,
                match_status=MatchStatusEnum.matched,
            )
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(corr_duplicate_sar)
                    await session.flush()

            # 9. Delete scene with sar_targets -> ForeignKeyViolation (RESTRICT)
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    await session.execute(delete(Scene).where(Scene.id == scene_id))
                    await session.flush()

            # 10. Delete sar_target with target_correlations -> ForeignKeyViolation (RESTRICT)
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    await session.execute(delete(SarTarget).where(SarTarget.id == sar_target_1_id))
                    await session.flush()

            # 11. Delete vessel with matched correlation -> vessel_id set to NULL
            # Note on constraints: chk_target_correlations_status_vessel enforces that
            # match_status='matched' rows must have vessel_id IS NOT NULL.
            # Thus, ON DELETE SET NULL on a 'matched' correlation triggers a CHECK violation.
            # To test ON DELETE SET NULL setting vessel_id to NULL, we test both:
            # A) Deleting vessel while match_status='matched' is rejected by the CHECK constraint.
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    await session.execute(delete(Vessel).where(Vessel.id == vessel_id))
                    await session.flush()

            # B) Creating a vessel linked to a correlation with 'borderline' status,
            # deleting that vessel cleanly triggers ON DELETE SET NULL, setting vessel_id to NULL.
            vessel_to_delete = Vessel(
                mmsi=str(random.randint(100_000_000, 999_999_999)),
                vessel_name=f"TEST DELETE VESSEL {rand_suffix}",
                vessel_type=VesselTypeEnum.cargo,
                source="ais",
            )
            session.add(vessel_to_delete)
            await session.commit()
            vessel_to_delete_id = vessel_to_delete.id
            created_vessel_ids.append(vessel_to_delete_id)

            corr_borderline = TargetCorrelation(
                sar_target_id=sar_target_3_id,
                vessel_id=vessel_to_delete_id,
                match_status=MatchStatusEnum.borderline,
            )
            session.add(corr_borderline)
            await session.commit()
            corr_borderline_id = corr_borderline.id
            created_correlation_ids.append(corr_borderline_id)

            # Now delete vessel_to_delete
            await session.execute(delete(Vessel).where(Vessel.id == vessel_to_delete_id))
            await session.commit()

            # Verify vessel_id is set to NULL in DB
            session.expire_all()
            reloaded_corr = await session.scalar(
                select(TargetCorrelation).where(TargetCorrelation.id == corr_borderline_id)
            )
            assert reloaded_corr is not None
            assert reloaded_corr.vessel_id is None
            assert reloaded_corr.match_status == MatchStatusEnum.borderline

        finally:
            # 12. Cleanup: target_correlations -> sar_targets -> vessels -> scenes
            try:
                if created_correlation_ids:
                    await session.execute(
                        delete(TargetCorrelation).where(TargetCorrelation.id.in_(created_correlation_ids))
                    )
                if created_sar_target_ids:
                    await session.execute(
                        delete(SarTarget).where(SarTarget.id.in_(created_sar_target_ids))
                    )
                if created_vessel_ids:
                    await session.execute(
                        delete(Vessel).where(Vessel.id.in_(created_vessel_ids))
                    )
                if created_scene_ids:
                    await session.execute(
                        delete(Scene).where(Scene.id.in_(created_scene_ids))
                    )
                await session.commit()
            except Exception:
                await session.rollback()
