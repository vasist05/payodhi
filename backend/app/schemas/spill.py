"""
backend/app/schemas/spill.py

Pydantic schemas for Spill entities and Phase-2 batch filtering contracts
(DataBaseFinal.md Table 4). Exactly 14 columns; wind context arrives via scene join.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.scene import SceneResponse

SpillStatus = Literal["detected", "under_review", "confirmed", "rejected"]


class SpillBase(BaseModel):
    scene_id: UUID
    spill_polygon: dict[str, Any] = Field(..., description="GeoJSON MultiPolygon, EPSG:4326")
    area_sq_km: float = Field(..., gt=0)
    detection_model_name: str
    detection_model_version: str
    confidence_score: float = Field(..., ge=0, le=1)
    processing_run_id: UUID | None = None
    status: SpillStatus = "detected"
    reviewed_by: str | None = None
    review_notes: str | None = None


class SpillCreate(SpillBase):
    pass


class SpillUpdate(BaseModel):
    status: SpillStatus | None = None
    reviewed_by: str | None = None
    review_notes: str | None = None


class SpillResponse(SpillBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    detected_at: datetime
    created_at: datetime
    updated_at: datetime
    scene: SceneResponse | None = None


# -------- Phase-2 filter batch contracts --------

class SpillCandidate(BaseModel):
    """Candidate detection proposed by Phase 1, consumed by Phase 2 filter."""
    patch_path: str
    center_lat: float
    center_lon: float
    scene_id: UUID
    spill_polygon: dict[str, Any]
    area_sq_km: float
    detection_confidence: float = Field(..., ge=0, le=1)


class SpillFilterBatchRequest(BaseModel):
    candidates: list[SpillCandidate] = Field(..., min_length=1)


class SpillFilterBatchResponse(BaseModel):
    confirmed: list[SpillResponse]
    rejected: list[SpillResponse]
    failed: list[dict[str, Any]] = []
    model_mode: Literal["sar_only", "sar_speed", "sar_uv"]
    calibration_temperature: float
