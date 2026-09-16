"""
backend/schemas.py
==================
Shared data contracts for the SIH26143 Oil Spill Attribution pipeline.

All phases (3, 4, 5, 6, 7) import from this single file.
This is the "handshake" file — when Phase 3 and Phase 4 finish,
they produce objects matching these dataclasses and Phase 5/6 work
immediately without any structural changes.

Integration points:
    Phase 3 (Drift)     → produces DriftResult
    Phase 4 (AIS)       → produces List[CandidateVessel]
    Phase 5 (Ranking)   → consumes both, produces List[AttributionResult]
    Phase 6 (Evidence)  → consumes List[AttributionResult], produces EvidenceReport
    Phase 7 (Dashboard) → consumes EvidenceReport for display / PDF
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Phase 3 Output — Drift Reconstruction
# ---------------------------------------------------------------------------

@dataclass
class OriginWindow:
    """
    Estimated spill origin time window and spatial region,
    produced by Phase 3 (backward drift simulation).
    """
    start_utc: str          # ISO-8601, e.g. "2018-07-12T14:05:00Z"
    end_utc: str            # ISO-8601, e.g. "2018-07-12T14:20:00Z"
    region_km_radius: float  # uncertainty radius around origin centroid (km)


@dataclass
class HeatmapPoint:
    """A single point in the origin probability heatmap (Phase 3 output)."""
    lat: float
    lon: float
    weight: float  # 0.0 – 1.0, higher = more probable origin location


@dataclass
class DriftResult:
    """
    Complete output of Phase 3 (Drift Reconstruction).
    Phase 5 consumes this to compute drift_agreement_score and time_overlap_score.

    Integration note for Phase 3 owner (Person 3):
        Populate and return a DriftResult from drift_sim.py.
        Phase 5 calls:  from backend.schemas import DriftResult
    """
    spill_detected_utc: str            # when the SAR image was captured
    spill_centroid_lat: float          # detected spill polygon centroid
    spill_centroid_lon: float
    origin_window: OriginWindow        # estimated release time + region
    origin_heatmap: List[HeatmapPoint] = field(default_factory=list)  # optional


# ---------------------------------------------------------------------------
# Phase 4 Output — AIS Correlation & Dark Vessel Detection
# ---------------------------------------------------------------------------

@dataclass
class CandidateVessel:
    """
    A single vessel candidate produced by Phase 4 (AIS pipeline).
    All fields are required; Phase 5 uses every field in scoring.

    Integration note for Phase 4 owner (Person 4):
        Build a list of CandidateVessel objects in backend/ais_pipeline/correlate.py.
        Phase 5 imports:  from backend.schemas import CandidateVessel

    Field descriptions
    ------------------
    mmsi                         : unique vessel identifier (9-digit string)
    name                         : vessel name from AIS static data
    type                         : vessel type string from AIS (e.g. "Oil tanker")
    flag                         : flag state ISO-2 code (e.g. "IN", "PA")
    position_lat / lon           : last known AIS position within origin time window
    distance_from_origin_km      : straight-line distance from Phase 3 origin centroid
    heading_deg                  : vessel heading at time of closest AIS position (0-359)
    speed_kts                    : vessel speed in knots at same timestamp
    ais_gap_minutes              : longest AIS signal gap during critical window (0 = none)
    dark_vessel                  : True if vessel appears in SAR but NOT in AIS
    behavioral_anomaly_score     : 0-100 score from Phase 4 anomaly detector (higher = more anomalous)
    cargo_history                : list of recent cargo types from port records (empty if unknown)
    bidirectional_drift_agreement: 0.0-1.0 — how well forward-drift-from-vessel matches actual spill
                                   (Phase 3 bidirectional check result); None if Phase 3 didn't run it
    """
    mmsi: str
    name: str
    type: str
    flag: str
    position_lat: float
    position_lon: float
    distance_from_origin_km: float
    heading_deg: float
    speed_kts: float
    ais_gap_minutes: int
    dark_vessel: bool
    behavioral_anomaly_score: float        # 0 – 100
    cargo_history: List[str] = field(default_factory=list)
    bidirectional_drift_agreement: Optional[float] = None  # 0.0 – 1.0, None if unavailable
    position_timestamp_utc: Optional[str] = None           # ISO-8601, when this AIS position was recorded


# ---------------------------------------------------------------------------
# High-pollution-risk vessel types & cargo (from maritime risk-profiling literature)
# ---------------------------------------------------------------------------

HIGH_RISK_TYPES = {
    "oil tanker", "chemical tanker", "chemical/oil tanker",
    "lpg tanker", "lng tanker", "products tanker",
    "oil/chemical tanker", "bunker vessel", "supply vessel",
    "oil products tanker", "tanker", "chemical"
}


HIGH_RISK_CARGO = {
    "crude oil", "fuel oil", "heavy fuel oil", "hsd", "hfo", "chemical",
    "lpg", "lng", "naphtha", "bitumen", "petroleum", "bunker oil",
    "furnace oil", "liquefied petroleum gas"
}


# ---------------------------------------------------------------------------
# Phase 5 Output — Attribution Ranking
# ---------------------------------------------------------------------------

class AttributionOutcome(str, Enum):
    STRONG        = "STRONG"        # one vessel clearly above others
    INCONCLUSIVE  = "INCONCLUSIVE"  # multiple vessels score similarly
    INSUFFICIENT  = "INSUFFICIENT"  # no candidate meets minimum threshold


@dataclass
class ScoreBreakdown:
    """Per-factor scores before weighting, for full transparency."""
    drift_agreement_score:       float  # 0.0 – 1.0
    time_overlap_score:          float  # 0.0 – 1.0
    spatial_proximity_score:     float  # 0.0 – 1.0
    vessel_characteristics_score: float # 0.0 – 1.0
    behavioral_anomaly_score:    float  # 0.0 – 1.0
    weighted_total:              float  # final 0–100 Attribution Score


@dataclass
class AttributionResult:
    """
    Single vessel's attribution result after Phase 5 scoring.
    Phase 6 (EvidenceBuilder) consumes a List[AttributionResult].
    """
    rank: int
    vessel: CandidateVessel
    attribution_score: float        # 0 – 100 (display value)
    score_breakdown: ScoreBreakdown
    outcome: AttributionOutcome     # set on the top-ranked result; INCONCLUSIVE / INSUFFICIENT for the list


# ---------------------------------------------------------------------------
# Phase 6 Output — Evidence Report
# ---------------------------------------------------------------------------

@dataclass
class EvidenceBullet:
    """A single evidence point (positive ✅ or negative ❌)."""
    positive: bool   # True = supports attribution, False = weakens/disqualifies
    text: str        # human-readable statement


@dataclass
class VesselEvidenceCard:
    """Full evidence card for one vessel (positive + negative bullets + narrative)."""
    vessel_name: str
    mmsi: str
    rank: int
    attribution_score: float
    outcome_label: str
    bullets: List[EvidenceBullet]
    narrative: str   # one-sentence human-readable summary
    disclaimer: str = (
        "Higher score indicates stronger evidentiary alignment; "
        "this is not a legal determination of responsibility."
    )


@dataclass
class EvidenceReport:
    """
    Full output of Phase 6.
    Consumed by Phase 7 (Dashboard) for display and PDF generation.

    Integration note for Phase 7 owner (Person 6):
        Import: from backend.schemas import EvidenceReport
        Receive via: from backend.run_attribution import run_full_pipeline
    """
    incident_id: str
    spill_detected_utc: str
    overall_outcome: AttributionOutcome
    primary_summary: str                        # top-level narrative sentence
    cards: List[VesselEvidenceCard]             # one card per candidate, ranked order
    total_candidates_evaluated: int
    model_version: str = "5.6-mock"             # updated when real data replaces mock
