"""
backend/app/schemas/drift.py

Pydantic schemas for Phase 3 Hydrodynamic Drift Reconstruction & Origin Estimation.
Follows DataBaseFinal.md Table 5 contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OriginEstimate(BaseModel):
    """Estimated origin coordinates and release time interval."""
    peak_lon: float = Field(..., description="Longitude of highest probability cell.")
    peak_lat: float = Field(..., description="Latitude of highest probability cell.")
    peak_prob: float = Field(..., description="Probability mass in peak cell.")
    release_window_start: datetime = Field(..., description="Earliest plausible release timestamp (UTC).")
    release_window_end: datetime = Field(..., description="Latest plausible release timestamp (UTC).")


class ConfidenceContour(BaseModel):
    """Ensemble cumulative probability contour bounding polygon."""
    level: float = Field(..., description="Cumulative probability level e.g. 0.50, 0.75, 0.90.")
    geometry: dict = Field(..., description="GeoJSON Polygon bounding the probability contour.")


class HeatmapSummary(BaseModel):
    """Summary metadata of the generated origin probability grid."""
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float
    resolution_deg: float
    grid_shape: List[int]
    total_runs: int
    successful_runs: int


class DriftRunRequest(BaseModel):
    """Request payload to trigger Phase 3 backward drift reconstruction."""
    scene_id: UUID
    spill_id: Optional[UUID] = None
    detection_lon: Optional[float] = None
    detection_lat: Optional[float] = None
    detection_time: Optional[datetime] = None
    window_hours: int = Field(12, ge=1, le=72, description="Backward time horizon in hours.")
    n_scenarios: int = Field(50, ge=5, le=500, description="Monte Carlo ensemble perturbations.")
    stokes_mode: Literal["wave", "windage", "tabular"] = Field("wave", description="Stokes drift physics mode.")
    force_rerun: bool = Field(False, description="If True, bypass idempotency cache.")


class DriftRunResponse(BaseModel):
    """Response payload returning drift reconstruction run result."""
    run_id: UUID
    scene_id: UUID
    spill_id: Optional[UUID] = None
    status: str
    run_fingerprint: str
    origin_estimate: Optional[OriginEstimate] = None
    contours: List[ConfidenceContour] = []
    heatmap_summary: Optional[HeatmapSummary] = None
    output_storage_uri: Optional[str] = None
    execution_time_ms: float
    message: str


class ForwardAttributionCandidateRequest(BaseModel):
    """Single candidate vessel position and release parameters for forward drift verification."""
    mmsi: str
    vessel_name: Optional[str] = ""
    vessel_lon: float
    vessel_lat: float
    release_time: datetime
    oil_type: str = "GENERIC MEDIUM CRUDE"


class ForwardAttributionRequest(BaseModel):
    """Request to score multiple candidate vessels against a detected spill."""
    scene_id: UUID
    spill_id: Optional[UUID] = None
    detection_lon: float
    detection_lat: float
    detection_time: datetime
    candidates: List[ForwardAttributionCandidateRequest]
    threshold_km: float = Field(30.0, ge=1.0, le=200.0)


class CandidateScoreResponse(BaseModel):
    """Forward drift agreement score for one candidate vessel."""
    mmsi: str
    vessel_name: str
    forward_score: float = Field(..., ge=0.0, le=1.0)
    distance_km: Optional[float] = None
    predicted_centroid: Optional[List[float]] = None
    release_time: str
    oil_type: str
    error: Optional[str] = None


class ForwardAttributionResponse(BaseModel):
    """Ranked vessel attribution outcomes."""
    scene_id: UUID
    spill_id: Optional[UUID] = None
    ranked_candidates: List[CandidateScoreResponse]
    outcome: str = Field(..., description="STRONG, INCONCLUSIVE, or INSUFFICIENT")
    reason: str
