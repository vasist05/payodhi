"""
End-to-end database workflow test.

Inserts:
  vessel → track → scene → spill → drift_run →
  attribution_score → dossier → audit_log

Then deletes in reverse FK order.
Prints WORKFLOW OK if every step passes.

Run from backend/ with:
    source .venv/bin/activate
    PYTHONPATH=$(pwd) python scripts/test_workflow.py
"""

import asyncio
import hashlib
import json
import random
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, text

from app.db.models import (
    AttributionScore,
    AuditLog,
    Dossier,
    DriftRun,
    Scene,
    Spill,
    Track,
    Vessel,
)
from app.db.models.enums import (
    ActorTypeEnum,
    AuditActionEnum,
    DossierStatusEnum,
    DriftStatusEnum,
    SceneStatusEnum,
    SpillStatusEnum,
    VerdictEnum,
    VesselTypeEnum,
)
from app.db.session import AsyncSessionLocal

# ── helpers ────────────────────────────────────────────────────────────────


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_point(lon: float, lat: float) -> str:
    """Return a WKT Point for ST_GeomFromText with SRID 4326."""
    return f"SRID=4326;POINT({lon} {lat})"


def make_multipolygon(lon: float, lat: float, delta: float = 0.01) -> str:
    """Return a trivial WKT MultiPolygon for spill_polygon."""
    return (
        f"SRID=4326;MULTIPOLYGON((("
        f"{lon} {lat},"
        f"{lon+delta} {lat},"
        f"{lon+delta} {lat+delta},"
        f"{lon} {lat+delta},"
        f"{lon} {lat}"
        f")))"
    )


def make_polygon(lon: float, lat: float, delta: float = 0.5) -> str:
    """Return a WKT Polygon for scene footprint."""
    return (
        f"SRID=4326;POLYGON(("
        f"{lon} {lat},"
        f"{lon+delta} {lat},"
        f"{lon+delta} {lat+delta},"
        f"{lon} {lat+delta},"
        f"{lon} {lat}"
        f"))"
    )


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


# ── main ───────────────────────────────────────────────────────────────────


async def run_workflow() -> None:
    print("=" * 60)
    print("  Payodhi DB End-to-End Workflow Test")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        async with session.begin():

            # ── 1. Vessel ───────────────────────────────────────
            print("\n[1/8] Inserting vessel …")
            rand_mmsi = str(random.randint(100_000_000, 999_999_999))  # 9 digits
            rand_imo  = str(random.randint(1_000_000, 9_999_999))      # 7 digits
            vessel = Vessel(
                mmsi=rand_mmsi,
                imo=rand_imo,
                vessel_name="MV Test Tanker",
                vessel_type=VesselTypeEnum.crude_tanker,
                flag_country_code="SG",
                source="manual",
                metadata_={"test": True},
            )
            session.add(vessel)
            await session.flush()  # get vessel.id without committing
            print(f"    vessel.id = {vessel.id}")

            # ── 2. Track ──────────────────────────────────────────────
            print("[2/8] Inserting track …")
            track = Track(
                vessel_id=vessel.id,
                recorded_at=utcnow(),
                position=text(f"ST_GeomFromEWKT('{make_point(103.8, 1.35)}')"),
                speed_knots=12.5,
                course_degrees=180.0,
                heading_degrees=179.0,
                navigational_status="underway",
                source="manual",
                source_record_id=str(uuid.uuid4()),
            )
            session.add(track)
            await session.flush()
            print(f"    track.id = {track.id}")

            # ── 3. Scene ──────────────────────────────────────────────
            print("[3/8] Inserting scene …")
            scene_hash = sha256_hex("test-scene-payload-2025")
            scene = Scene(
                source_provider="CDSE",
                external_scene_id=f"TEST-SCENE-{uuid.uuid4().hex[:8].upper()}",
                captured_at=utcnow(),
                footprint=text(f"ST_GeomFromEWKT('{make_polygon(103.7, 1.3)}')"),
                sha256=scene_hash,
                processing_status=SceneStatusEnum.processed,
                storage_uri="minio://payodi-scenes/test/scene.tif",
                source_metadata={"sensor": "SAR"},
            )
            session.add(scene)
            await session.flush()
            print(f"    scene.id = {scene.id}")

            # ── 4. Spill ──────────────────────────────────────────────
            print("[4/8] Inserting spill …")
            spill = Spill(
                scene_id=scene.id,
                spill_polygon=text(
                    f"ST_GeomFromEWKT('{make_multipolygon(103.78, 1.33)}')"
                ),
                area_sq_km=2.450,
                detection_model_name="OilNet",
                detection_model_version="1.2.0",
                confidence_score=0.92,
                status=SpillStatusEnum.confirmed,
            )
            session.add(spill)
            await session.flush()
            print(f"    spill.id = {spill.id}")

            # ── 5. Drift Run ──────────────────────────────────────────
            print("[5/8] Inserting drift_run …")
            fingerprint = sha256_hex(
                f"{scene.id}{vessel.id}{spill.id}{utcnow().isoformat()}"
            )
            drift_run = DriftRun(
                scene_id=scene.id,
                vessel_id=vessel.id,
                spill_id=spill.id,
                simulation_version="v1.0.0",
                model_parameters={"wind_drag": 0.03, "diffusion_coeff": 0.1},
                run_fingerprint=fingerprint,
                status=DriftStatusEnum.completed,
                output_storage_uri="minio://payodi-scenes/drift/output.json",
                output_sha256=sha256_hex("drift-output-content"),
                result_summary={"matched": True},
            )
            session.add(drift_run)
            await session.flush()
            print(f"    drift_run.id = {drift_run.id}")

            # ── 6. Attribution Score ──────────────────────────────────
            print("[6/8] Inserting attribution_score …")
            score = AttributionScore(
                drift_run_id=drift_run.id,
                scoring_version="v1.0.0",
                cpa_score=0.85,
                dark_vessel_score=0.90,
                loitering_score=0.70,
                capacity_multiplier=1.0,
                draft_change_score=0.65,
                permutation_p_value=0.02000,
                stability_index=0.88,
                total_score=82.50,
                verdict=VerdictEnum.prosecutable,
                explanation={
                    "pillar1": "CPA < 2km",
                    "pillar2": "AIS gap 4h in open water",
                    "pillar3": "Loitering 3h",
                    "pillar4": "Capacity confirmed",
                    "pillar5": "Draft change detected",
                    "pillar6": "p < 0.05",
                    "pillar7": "Stable across bootstrap",
                },
            )
            session.add(score)
            await session.flush()
            print(f"    attribution_score.id = {score.id}")

            # ── 7. Dossier ────────────────────────────────────────────
            print("[7/8] Inserting dossier …")
            evidence = {
                "vessel_id": str(vessel.id),
                "scene_id": str(scene.id),
                "verdict": "prosecutable",
                "total_score": 82.5,
            }
            dossier_hash = sha256_hex(json.dumps(evidence, sort_keys=True))
            dossier = Dossier(
                scene_id=scene.id,
                spill_id=spill.id,
                dossier_version="v1.0.0",
                generated_by="system:test_workflow",
                storage_uri="minio://payodi-dossiers/test/dossier-v1.pdf",
                sha256=dossier_hash,
                evidence_snapshot=evidence,
                status=DossierStatusEnum.draft,
            )
            session.add(dossier)
            await session.flush()
            print(f"    dossier.id = {dossier.id}")

            # ── 8. Audit Log ──────────────────────────────────────────
            print("[8/8] Inserting audit_log …")
            payload = json.dumps(
                {"entity": "vessel", "id": str(vessel.id), "action": "create"},
                sort_keys=True,
            )
            event_hash = sha256_hex(payload)
            audit = AuditLog(
                actor_type=ActorTypeEnum.system,
                actor_id="test_workflow.py",
                action=AuditActionEnum.create,
                entity_type="vessels",
                entity_id=vessel.id,
                after_data={"vessel_name": "MV Test Tanker"},
                metadata_={"source": "e2e_test"},
                event_hash=event_hash,
            )
            session.add(audit)
            await session.flush()
            print(f"    audit_log.id = {audit.id}")

            # ── Capture IDs before deletion ────────────────────────────
            ids = {
                "audit": audit.id,
                "dossier": dossier.id,
                "score": score.id,
                "drift_run": drift_run.id,
                "spill": spill.id,
                "scene": scene.id,
                "track": track.id,
                "vessel": vessel.id,
            }

        # ── Verify audit_log append-only trigger ──────────────────────
        print("\n[VERIFY] Testing audit_log append-only trigger …")
        async with session.begin():
            try:
                await session.execute(
                    delete(AuditLog).where(AuditLog.id == ids["audit"])
                )
                # If we get here the trigger is missing — that's a failure
                raise AssertionError("audit_log DELETE was NOT blocked — trigger missing!")
            except AssertionError:
                raise
            except Exception as e:
                if "append-only" in str(e):
                    print("    ✓ audit_log DELETE correctly blocked by trigger")
                else:
                    raise

        # ── Cleanup: delete in reverse FK order (audit_log stays) ──────
        print("[CLEANUP] Deleting test rows in reverse FK order …")
        print("    (audit_log rows are permanent by design — skipped)")
        async with session.begin():
            await session.execute(
                delete(Dossier).where(Dossier.id == ids["dossier"])
            )
            await session.execute(
                delete(AttributionScore).where(AttributionScore.id == ids["score"])
            )
            await session.execute(
                delete(DriftRun).where(DriftRun.id == ids["drift_run"])
            )
            await session.execute(
                delete(Spill).where(Spill.id == ids["spill"])
            )
            await session.execute(
                delete(Scene).where(Scene.id == ids["scene"])
            )
            await session.execute(
                delete(Track).where(Track.id == ids["track"])
            )
            await session.execute(
                delete(Vessel).where(Vessel.id == ids["vessel"])
            )
        print("    All mutable test rows deleted.")

    print("\n" + "=" * 60)
    print("  WORKFLOW OK")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(run_workflow())
    except Exception as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
