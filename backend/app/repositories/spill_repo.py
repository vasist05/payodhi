"""
backend/app/repositories/spill_repo.py

Repository for oil spill detections (DataBaseFinal.md Table 4).
Strictly 14 columns; wind context is read exclusively via eager-loaded scene JOIN.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.spill import Spill
from app.repositories.base import AsyncRepository


class SpillRepository(AsyncRepository[Spill]):
    model = Spill

    async def create_spill(
        self,
        *,
        scene_id: UUID,
        spill_polygon_wkt: str,
        area_sq_km: float,
        detection_model_name: str,
        detection_model_version: str,
        confidence_score: float,
        status: str = "detected",
        review_notes: str | None = None,
        processing_run_id: UUID | None = None,
    ) -> Spill:
        """Insert one spill row adhering strictly to the Table 4 contract."""
        spill = Spill(
            scene_id=scene_id,
            spill_polygon=func.ST_GeomFromText(spill_polygon_wkt, 4326),
            area_sq_km=area_sq_km,
            detection_model_name=detection_model_name,
            detection_model_version=detection_model_version,
            confidence_score=confidence_score,
            status=status,
            review_notes=review_notes,
            processing_run_id=processing_run_id,
        )
        return await self.add(spill)

    async def get_with_scene(self, spill_id: UUID) -> Spill | None:
        """Eager-load scene so wind context is available without N+1 queries."""
        stmt = (
            select(Spill)
            .options(selectinload(Spill.scene))
            .where(Spill.id == spill_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_with_scene(
        self,
        *,
        status: str | None = None,
        scene_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Spill]:
        """Query spills with eager-loaded scene, filtered by status or scene_id."""
        stmt = select(Spill).options(selectinload(Spill.scene))
        if status is not None:
            stmt = stmt.where(Spill.status == status)
        if scene_id is not None:
            stmt = stmt.where(Spill.scene_id == scene_id)
        stmt = stmt.limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_status(
        self,
        spill_id: UUID,
        *,
        status: str,
        reviewed_by: str | None = None,
        review_notes: str | None = None,
    ) -> Spill | None:
        """Update spill verification status and review feedback."""
        spill = await self.get_by_id(spill_id)
        if spill is None:
            return None
        spill.status = status
        if reviewed_by is not None:
            spill.reviewed_by = reviewed_by
        if review_notes is not None:
            spill.review_notes = review_notes
        await self.session.flush()
        return spill
