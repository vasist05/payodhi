"""
backend/app/schemas/scene.py

Pydantic schemas for satellite scene metadata (DataBaseFinal.md Table 3).
Computes directional wind vector components (U10, V10) on read without DB schema drift.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


class SceneBase(BaseModel):
    source_provider: str
    external_scene_id: str
    captured_at: datetime
    footprint: dict[str, Any] = Field(..., description="GeoJSON Polygon, EPSG:4326")
    cloud_cover_percentage: float | None = Field(None, ge=0, le=100)
    wind_speed: float | None = Field(None, ge=0)
    wind_direction: float | None = Field(None, ge=0, le=360)
    storage_uri: str
    sha256: str = Field(..., min_length=64, max_length=64)
    processing_status: str = "pending"
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class SceneCreate(SceneBase):
    pass


class SceneResponse(SceneBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingested_at: datetime
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def wind_u10(self) -> float | None:
        """Derived eastward component. Not stored in DB — computed on read."""
        if self.wind_speed is None or self.wind_direction is None:
            return None
        return float(self.wind_speed) * math.sin(math.radians(float(self.wind_direction)))

    @computed_field
    @property
    def wind_v10(self) -> float | None:
        """Derived northward component. Not stored in DB — computed on read."""
        if self.wind_speed is None or self.wind_direction is None:
            return None
        return float(self.wind_speed) * math.cos(math.radians(float(self.wind_direction)))
