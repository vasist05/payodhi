"""
backend/app/schemas/pipeline.py

Pydantic schemas for the Unified Phase 1 + 2 + 3 End-to-End Maritime Oil Spill Pipeline.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.drift import DriftRunResponse
from app.schemas.spill import SpillResponse


class IntegratedPipelineRequest(BaseModel):
    """Request payload to execute the full Phase 1 (Detection) -> Phase 2 (Filter) -> Phase 3 (Drift) -> Phase 4 (AIS) -> Phase 5 (Attribution) -> Phase 8 (Coast Guard Response) chain."""
    scene_id: UUID
    image_path: Optional[str] = Field(
        None,
        description="Optional local file path or storage URI override for the SAR scene raster."
    )
    detection_threshold: float = Field(0.50, ge=0.0, le=1.0, description="U-Net probability threshold.")
    min_pixels: int = Field(50, ge=1, description="Minimum connected component size.")
    filter_mode: Literal["sar_only", "sar_speed", "sar_uv"] = Field(
        "sar_uv",
        description="Phase 2 false-positive filter model mode (SAR-UV recommended)."
    )
    drift_window_hours: int = Field(12, ge=1, le=72, description="Backward drift simulation horizon in hours.")
    n_drift_scenarios: int = Field(50, ge=5, le=300, description="Ensemble size for backward Monte Carlo.")
    stokes_mode: Literal["wave", "windage", "tabular"] = Field("wave", description="Stokes drift physics mode.")
    run_phase4_ais: bool = Field(True, description="Whether to execute Phase 4 AIS correlation and dark vessel detection.")
    run_phase5_attribution: bool = Field(True, description="Whether to execute Phase 5 7-pillar forensic attribution.")
    run_phase8_response: bool = Field(True, description="Whether to evaluate safety gates and trigger Coast Guard response.")


class IntegratedPipelineResponse(BaseModel):
    """Unified response containing detections, confirmed/rejected spills, origin drift reconstructions, AIS correlations, attributions, and tactical response."""
    scene_id: UUID
    status: str
    spill_count_detected: int
    spill_count_confirmed: int
    spill_count_rejected: int
    confirmed_spills: List[SpillResponse]
    rejected_lookalikes: List[SpillResponse]
    drift_reconstructions: List[DriftRunResponse]
    ais_correlations: Optional[Dict[str, Any]] = None
    attribution_results: Optional[List[Dict[str, Any]]] = None
    response_alert: Optional[Dict[str, Any]] = None
    total_execution_time_ms: float
    message: str

