import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure project root is on sys.path so core and backend packages are importable
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.models.drift_run import DriftRun
from app.db.models.scene import Scene
from app.db.models.spill import Spill
from app.db.models.vessel import Vessel
from app.services.attribution_service import (
    load_ais_gaps,
    load_draft_history,
    load_drift_trajectory,
    load_port_polygons,
    load_vessel_meta,
    load_vessel_track,
    persist_attribution_score,
    persist_cpa_event,
    write_audit_log,
)
from core.phase5_attribution.calibration import calibrate_score
from core.phase5_attribution.fusion import fuse_scores
from core.phase5_attribution.pillar1_cpa import calculate_cpa
from core.phase5_attribution.pillar2_dark_vessel import detect_dark_window
from core.phase5_attribution.pillar3_loitering import detect_loitering
from core.phase5_attribution.pillar4_capacity_veto import capacity_veto
from core.phase5_attribution.pillar5_draft_change import draft_change_score
from core.phase5_attribution.pillar6_permutation import permutation_test
from core.phase5_attribution.pillar7_sensitivity import sensitivity_test
from core.phase5_attribution.verdict import classify_verdict

logger = logging.getLogger(__name__)


async def run_attribution(
    session: AsyncSession,
    drift_run_id: UUID,
    scoring_version: str = "v1.0.0",
) -> Dict[str, Any]:
    """Execute end-to-end 7-pillar evidential attribution pipeline for a drift run."""
    try:
        # 1. Fetch DriftRun by id
        stmt = select(DriftRun).where(DriftRun.id == drift_run_id)
        res = await session.execute(stmt)
        drift_run = res.scalar_one_or_none()
        if not drift_run:
            raise ValueError("drift_run_not_found")

        # 2. Fetch Scene, Vessel, Spill via drift_run FKs
        scene = await session.get(Scene, drift_run.scene_id)
        vessel = await session.get(Vessel, drift_run.vessel_id)
        spill = await session.get(Spill, drift_run.spill_id) if drift_run.spill_id else None

        # 3. If no Spill
        if not spill:
            return {
                "drift_run_id": drift_run_id,
                "total_score": 0.0,
                "calibrated_score": 0.0,
                "verdict": "insufficient_evidence",
                "reason": "no_spill_linked",
            }

        # 4. scene_time = scene.captured_at
        scene_time = scene.captured_at if (scene and scene.captured_at) else datetime.now(timezone.utc)
        if scene_time.tzinfo is None:
            scene_time = scene_time.replace(tzinfo=timezone.utc)

        # 5. spill_center = ST_Centroid(spill.spill_polygon) → extract lat/lon
        centroid_stmt = select(
            func.ST_Y(func.ST_Centroid(spill.spill_polygon)).label("lat"),
            func.ST_X(func.ST_Centroid(spill.spill_polygon)).label("lon"),
        )
        c_res = await session.execute(centroid_stmt)
        c_row = c_res.first()
        if c_row and c_row.lat is not None and c_row.lon is not None:
            spill_center = {"lat": float(c_row.lat), "lon": float(c_row.lon)}
        else:
            spill_center = {"lat": 0.0, "lon": 0.0}

        # 6. Load all inputs
        tracks = await load_vessel_track(session, drift_run.vessel_id, scene_time, window_hours=6)
        drift_trajectory = await load_drift_trajectory(session, drift_run_id)
        vessel_meta = await load_vessel_meta(session, drift_run.vessel_id)
        gaps = await load_ais_gaps(session, drift_run.vessel_id, scene_time, window_hours=6)
        drafts = await load_draft_history(session, drift_run.vessel_id, scene_time, window_hours=48)
        ports = await load_port_polygons()

        # 7. If no tracks OR no drift_trajectory
        if not tracks or not drift_trajectory:
            return {
                "drift_run_id": drift_run_id,
                "total_score": 0.0,
                "calibrated_score": 0.0,
                "verdict": "insufficient_evidence",
                "reason": "no_track_or_drift_data",
            }

        # 8. Run Pillars 1-5 individually
        # Pillar 1 (CPA)
        try:
            p1_res = calculate_cpa(
                vessel_track=tracks,
                drift_trajectory=drift_trajectory,
                reference_time=scene_time,
            )
        except Exception as e:
            logger.exception("Pillar 1 CPA failed: %s", e)
            p1_res = {"cpa_score": 0.0, "reason": f"pillar_failed: {e}"}

        # Pillar 2 (Dark Vessel)
        try:
            p2_res = detect_dark_window(
                vessel_track=tracks,
                spill_center=spill_center,
                spill_time=scene_time,
            )
        except Exception as e:
            logger.exception("Pillar 2 Dark Vessel failed: %s", e)
            p2_res = {"dark_vessel_score": 0.0, "reason": f"pillar_failed: {e}"}

        # Pillar 3 (Loitering)
        try:
            p3_res = detect_loitering(
                vessel_track=tracks,
                sar_time=scene_time,
                port_polygons=ports,
                vessel_type=vessel_meta.get("vessel_type"),
            )
        except Exception as e:
            logger.exception("Pillar 3 Loitering failed: %s", e)
            p3_res = {"loitering_score": 0.0, "reason": f"pillar_failed: {e}"}

        # Pillar 4 (Capacity Veto)
        try:
            spill_area_m2 = float(spill.area_sq_km) * 1e6 if spill.area_sq_km is not None else 10000.0
            p4_res = capacity_veto(
                spill_area_m2=spill_area_m2,
                vessel_dwt=vessel_meta.get("deadweight_tonnage"),
                vessel_type=vessel_meta.get("vessel_type", "unknown"),
            )
        except Exception as e:
            logger.exception("Pillar 4 Capacity Veto failed: %s", e)
            p4_res = {"multiplier": 1.0, "db_multiplier": 1, "reason": f"pillar_failed: {e}"}

        # Pillar 5 (Draft Change)
        try:
            p5_res = draft_change_score(
                vessel_static_history=drafts,
                spill_time=scene_time,
                vessel_type=vessel_meta.get("vessel_type"),
            )
        except Exception as e:
            logger.exception("Pillar 5 Draft Change failed: %s", e)
            p5_res = {"draft_change_score": 0.0, "reason": f"pillar_failed: {e}"}

        # 9. Pillar 4 check
        db_multiplier = p4_res.get("db_multiplier", 1.0)
        if db_multiplier == 0.0 or db_multiplier == 0:
            total_score = 0.0
            p_value = 1.0
            stability_index = 0.0
            p6_res = {"p_value": 1.0, "reason": "capacity_vetoed"}
            p7_res = {"stability_index": 0.0, "reason": "capacity_vetoed"}
        else:
            proxy_scores = [
                float(p1_res.get("cpa_score", 0.0) or 0.0),
                float(p2_res.get("dark_vessel_score", 0.0) or 0.0),
                float(p3_res.get("loitering_score", 0.0) or 0.0),
                float(p5_res.get("draft_change_score", 0.0) or 0.0),
            ]
            pillar_score_proxy = sum(proxy_scores) / max(len(proxy_scores), 1)

            # Pillar 6: permutation_test
            try:
                p6_res = permutation_test({str(drift_run.vessel_id): pillar_score_proxy})
                p_value = float(p6_res.get("p_value", 1.0))
            except Exception as e:
                logger.exception("Pillar 6 Permutation failed: %s", e)
                p6_res = {"p_value": 1.0, "reason": f"pillar_failed: {e}"}
                p_value = 1.0

            # Pillar 7: sensitivity_test
            try:
                p7_res = sensitivity_test(
                    run_drift_fn=lambda w, c: {str(drift_run.vessel_id): pillar_score_proxy},
                    n_runs=100,
                )
                stability_index = float(p7_res.get("stability_index", 0.0))
            except Exception as e:
                logger.exception("Pillar 7 Sensitivity failed: %s", e)
                p7_res = {"stability_index": 0.0, "reason": f"pillar_failed: {e}"}
                stability_index = 0.0

        # 10. Fusion
        pillars = {
            "pillar1_cpa": p1_res,
            "pillar2_dark": p2_res,
            "pillar3_loiter": p3_res,
            "pillar4_capacity": p4_res,
            "pillar5_draft": p5_res,
            "pillar6_permutation": p6_res,
            "pillar7_sensitivity": p7_res,
        }
        fusion_result = fuse_scores(pillars)
        if db_multiplier == 0.0 or db_multiplier == 0:
            total_score = 0.0
        else:
            total_score = float(fusion_result.get("total_score", 0.0))

        # 11. Calibration
        calibrated_score = float(calibrate_score(total_score / 100.0) * 100.0)

        # 12. Verdict
        verdict_ctx = "capacity_veto" if (db_multiplier == 0.0 or db_multiplier == 0) else None
        verdict_result = classify_verdict(
            calibrated_score=calibrated_score / 100.0,
            p_value=p_value,
            stability_index=stability_index,
            reason_context=verdict_ctx,
        )

        # 13. If pillar1 succeeded → persist_cpa_event
        if (
            p1_res.get("min_distance_m") is not None
            and p1_res.get("vessel_point")
            and p1_res.get("drift_point")
        ):
            try:
                await persist_cpa_event(session, drift_run_id, drift_run.vessel_id, p1_res)
            except Exception as e:
                logger.exception("Persisting CPA event failed: %s", e)

        # 14. persist_attribution_score
        score_id = await persist_attribution_score(
            session=session,
            drift_run_id=drift_run_id,
            scoring_version=scoring_version,
            pillars=pillars,
            fusion_result={"total_score": total_score, "calibrated_score": calibrated_score},
            verdict_result=verdict_result,
        )

        # 15. write_audit_log
        audit_payload = {
            "score_id": str(score_id),
            "drift_run_id": str(drift_run_id),
            "scoring_version": scoring_version,
            "total_score": round(total_score, 2),
            "calibrated_score": round(calibrated_score, 2),
            "verdict": verdict_result.get("db_verdict"),
            "p_value": round(p_value, 5),
            "stability_index": round(stability_index, 3),
        }
        await write_audit_log(session, "attribution_score", score_id, "create", audit_payload)

        # 16. session.commit()
        await session.commit()

        # 17. Return summary
        return {
            "drift_run_id": drift_run_id,
            "total_score": total_score,
            "calibrated_score": calibrated_score,
            "verdict": verdict_result.get("db_verdict"),
            "reason": verdict_result.get("reason", ""),
        }

    except Exception:
        await session.rollback()
        raise
