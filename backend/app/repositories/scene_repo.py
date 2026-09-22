"""
backend/app/repositories/scene_repo.py

Repository for satellite scene records (DataBaseFinal.md Table 3).
Stores footprint and wind context (wind_speed, wind_direction).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import SceneStatusEnum
from app.db.models.scene import Scene
from app.repositories.base import AsyncRepository


class SceneRepository(AsyncRepository[Scene]):
    model = Scene

    async def create_scene(
        self,
        *,
        source_provider: str,
        external_scene_id: str,
        captured_at: datetime,
        footprint_wkt: str,
        storage_uri: str,
        sha256: str,
        wind_speed: float | None = None,
        wind_direction: float | None = None,
        cloud_cover_percentage: float | None = None,
        source_metadata: dict | None = None,
        processing_status: SceneStatusEnum = SceneStatusEnum.pending,
    ) -> Scene:
        scene = Scene(
            source_provider=source_provider,
            external_scene_id=external_scene_id,
            captured_at=captured_at,
            footprint=func.ST_GeomFromText(footprint_wkt, 4326),
            storage_uri=storage_uri,
            sha256=sha256,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            cloud_cover_percentage=cloud_cover_percentage,
            source_metadata=source_metadata or {},
            processing_status=processing_status,
        )
        return await self.add(scene)

    async def get_by_external_id(
        self, source_provider: str, external_scene_id: str
    ) -> Scene | None:
        stmt = select(Scene).where(
            Scene.source_provider == source_provider,
            Scene.external_scene_id == external_scene_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def update_status(
        self, scene_id: UUID, status: SceneStatusEnum
    ) -> Scene | None:
        scene = await self.get_by_id(scene_id)
        if scene is not None:
            scene.processing_status = status
            await self.session.flush()
        return scene
