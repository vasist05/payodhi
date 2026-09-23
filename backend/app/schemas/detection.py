"""
backend/app/schemas/detection.py

Pydantic schemas for Phase 1 SAR Oil Spill Detection API.
Adheres to DataBaseFinal.md contracts for scenes (Table 3) and spills (Table 4).
"""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.spill import SpillCandidate, SpillResponse


class DetectionRunRequest(BaseModel):
    """Request payload to run Phase 1 SAR spill detection on a scene."""
    scene_id: UUID
    image_path: Optional[str] = Field(
        None,
        description="Optional local filesystem path or override URI for the SAR scene raster."
    )
    threshold: float = Field(0.50, ge=0.0, le=1.0, description="Probability cutoff for oil pixels.")
    min_pixels: int = Field(50, ge=1, description="Minimum connected component size to reject speckle noise.")
    auto_trigger_filter: bool = Field(
        False,
        description="If True, automatically pipes candidate detections into Phase 2 False-Positive Filter."
    )


class DetectionRunResponse(BaseModel):
    """Response payload returning detected spills and exported Phase 2 candidates."""
    scene_id: UUID
    spill_count: int
    spills: List[SpillResponse]
    candidates: List[SpillCandidate] = []
    status: str
    message: str
