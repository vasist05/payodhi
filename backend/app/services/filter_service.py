"""
backend/app/services/filter_service.py

Phase-2 False-Positive Filter service layer.

Bridges the Phase-2 ML classifier (core/phase2_false_positive/) with the
PostgreSQL/TimescaleDB persistence layer, honoring the schema contract in
docs/guides/DataBaseFinal.md.

Wind resolution is HYBRID:
  1. Primary:  derive (u10, v10) from scenes.wind_speed + scenes.wind_direction
  2. Fallback: look up exact historical ERA5 vector from
               data/fp_filter/wind_metadata.json (CSIRO benchmark patches)

No new columns on `spills`. Wind context is read via JOIN to `scenes`.
Rejection rationale is written to `spills.review_notes`.
Audit entries go to `audit_log` (singular) via hash-chained append.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.phase2_false_positive.inference import SpillFilter
from app.repositories.audit_repo import AuditRepository
from app.repositories.scene_repo import SceneRepository
from app.repositories.spill_repo import SpillRepository
from app.schemas.common import geojson_to_wkt

log = logging.getLogger(__name__)

MODEL_NAME = "SpillFilterNet"
MODEL_VERSION = "sar_uv-v1"

# Path to the CSIRO per-patch wind metadata used as a fallback when the
# scene row does not carry wind_speed / wind_direction. Loaded lazily once.
_WIND_METADATA_PATH = Path("data/fp_filter/wind_metadata.json")


class FilterService:
    """
    Applies the Phase-2 SAR-UV classifier to candidate spill detections,
    persists results to `spills`, and writes an immutable audit entry.

    All writes happen inside one transaction and are committed at the end
    of `filter_batch`. If any candidate fails, the failure is captured but
    the transaction continues for the remaining candidates.
    """

    def __init__(self, session: AsyncSession, mode: str = "sar_uv"):
        if mode not in ("sar_only", "sar_speed", "sar_uv"):
            raise ValueError(f"unsupported mode: {mode}")
        self.session = session
        self.mode = mode

        self.spills = SpillRepository(session)
        self.scenes = SceneRepository(session)
        self.audit = AuditRepository(session)

        self._filter: SpillFilter | None = None
        self._wind_metadata: dict | None = None

    # ------------------------------------------------------------------ #
    # Lazy-loaded resources
    # ------------------------------------------------------------------ #

    def _get_filter(self) -> SpillFilter:
        """Lazy-init SpillFilter (heavy: torch + checkpoint load)."""
        if self._filter is None:
            log.info("Initializing SpillFilter (mode=%s)…", self.mode)
            self._filter = SpillFilter(mode=self.mode)
        return self._filter

    def _get_wind_metadata(self) -> dict:
        """Lazy-load CSIRO per-patch wind metadata (fallback source)."""
        if self._wind_metadata is None:
            if _WIND_METADATA_PATH.exists():
                with open(_WIND_METADATA_PATH, "r", encoding="utf-8") as f:
                    self._wind_metadata = json.load(f)
                log.info(
                    "Loaded wind_metadata.json (%d patches)",
                    len(self._wind_metadata),
                )
            else:
                log.warning(
                    "wind_metadata.json not found at %s — fallback disabled",
                    _WIND_METADATA_PATH,
                )
                self._wind_metadata = {}
        return self._wind_metadata

    # ------------------------------------------------------------------ #
    # Wind resolution (HYBRID)
    # ------------------------------------------------------------------ #

    def _resolve_wind(
        self,
        *,
        scene,                  # app.db.models.scene.Scene
        patch_path: str,
    ) -> tuple[float | None, float | None, str]:
        """
        Resolve (u10, v10) for one patch.

        Priority order:
          1. scenes.wind_speed + scenes.wind_direction  → derive U/V
          2. data/fp_filter/wind_metadata.json[filename] → exact ERA5 lookup
          3. (None, None)                                → filter uses internal default

        Returns:
            (u10, v10, source_tag)
            source_tag ∈ {"scene_derived", "metadata_json", "none"}
        """
        # --- Tier 1: scene-derived (production / API path) ---------------
        if scene.wind_speed is not None and scene.wind_direction is not None:
            # Compass convention: direction is where wind blows FROM.
            # East component  = speed · sin(direction)
            # North component = speed · cos(direction)
            u10 = float(scene.wind_speed) * math.sin(
                math.radians(float(scene.wind_direction))
            )
            v10 = float(scene.wind_speed) * math.cos(
                math.radians(float(scene.wind_direction))
            )
            return u10, v10, "scene_derived"

        # --- Tier 2: CSIRO per-patch metadata fallback -------------------
        filename = Path(patch_path).name
        meta = self._get_wind_metadata().get(filename)
        if meta and meta.get("u10") is not None and meta.get("v10") is not None:
            return float(meta["u10"]), float(meta["v10"]), "metadata_json"

        # --- Tier 3: no wind available -----------------------------------
        log.debug("No wind context for %s — using filter default", filename)
        return None, None, "none"

    # ------------------------------------------------------------------ #
    # Batch entrypoint
    # ------------------------------------------------------------------ #

    async def filter_batch(
        self,
        candidates: list[dict],
        *,
        request_id: UUID | None = None,
        actor_id: str | None = None,
    ) -> dict:
        """
        Run Phase-2 filter over a batch of candidates, persist confirmed and
        rejected rows to `spills`, and append audit entries.

        Each candidate is:
            {
              "patch_path": str,
              "scene_id": UUID,
              "spill_polygon": dict,   # GeoJSON MultiPolygon
              "area_sq_km": float,
              "detection_confidence": float,
              "center_lat": float,
              "center_lon": float,
            }

        Returns:
            {
              "confirmed": list[Spill],
              "rejected":  list[Spill],
              "failed":    list[dict],   # one entry per candidate that raised
              "model_mode": str,
              "calibration_temperature": float,
            }
        """
        f = self._get_filter()
        confirmed: list = []
        rejected: list = []
        failed: list[dict] = []

        for cand in candidates:
            patch_path = cand["patch_path"]
            scene_id = cand["scene_id"]

            try:
                scene = await self.scenes.get_by_id(scene_id)
                if scene is None:
                    raise ValueError(f"scene {scene_id} not found")

                u10, v10, wind_source = self._resolve_wind(
                    scene=scene, patch_path=patch_path
                )

                result = f.verify_single(
                    patch_path=patch_path,
                    wind_u10=u10,
                    wind_v10=v10,
                )

                is_oil = bool(result["is_oil"])
                prob = float(result["confidence"])

                spill = await self.spills.create_spill(
                    scene_id=scene_id,
                    spill_polygon_wkt=geojson_to_wkt(cand["spill_polygon"]),
                    area_sq_km=float(cand["area_sq_km"]),
                    detection_model_name=MODEL_NAME,
                    detection_model_version=MODEL_VERSION,
                    confidence_score=prob,
                    status="confirmed" if is_oil else "rejected",
                    review_notes=(
                        None
                        if is_oil
                        else f"Lookalike detected (P(oil)={prob:.3f})"
                    ),
                    # NO wind_u10, NO wind_v10, NO wind_speed,
                    # NO rejection_reason — banned on spills.
                )

                await self.audit.append(
                    actor_type="system",
                    actor_id=actor_id,
                    action="create",
                    entity_type="spills",
                    entity_id=spill.id,
                    request_id=request_id,
                    after={
                        "status": spill.status,
                        "confidence": prob,
                    },
                    metadata={
                        "model": MODEL_NAME,
                        "version": MODEL_VERSION,
                        "mode": self.mode,
                        "wind_source": wind_source,
                    },
                )

                (confirmed if is_oil else rejected).append(spill)

            except Exception as exc:  # noqa: BLE001 — per-candidate isolation
                log.exception(
                    "Filter failed for patch=%s scene=%s",
                    cand.get("patch_path"),
                    cand.get("scene_id"),
                )
                failed.append(
                    {
                        "patch_path": cand.get("patch_path"),
                        "scene_id": str(cand.get("scene_id")),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue

        await self.session.commit()

        return {
            "confirmed": confirmed,
            "rejected": rejected,
            "failed": failed,
            "model_mode": self.mode,
            "calibration_temperature": float(getattr(f, "T", 1.0)),
        }
