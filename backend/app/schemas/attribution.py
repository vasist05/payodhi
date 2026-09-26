from datetime import datetime
from decimal import Decimal
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttributionRunRequest(BaseModel):
    scoring_version: str = "v1.0.0"


class AttributionScoreResponse(BaseModel):
    id: UUID
    drift_run_id: UUID
    scoring_version: str
    cpa_score: Decimal
    dark_vessel_score: Decimal
    loitering_score: Decimal
    capacity_multiplier: Decimal
    draft_change_score: Decimal
    permutation_p_value: Decimal
    stability_index: Decimal
    total_score: Decimal
    verdict: str
    explanation: dict
    calculated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CpaEventResponse(BaseModel):
    id: UUID
    drift_run_id: UUID
    vessel_id: UUID
    min_distance_m: Decimal
    cpa_timestamp: datetime
    tcpa_seconds: Decimal
    vessel_position_at_cpa: dict
    slick_position_at_cpa: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
