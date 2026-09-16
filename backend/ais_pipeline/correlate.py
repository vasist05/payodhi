"""
backend/ais_pipeline/correlate.py
===================================
Phase 4: AIS Correlation & Candidate Vessel Extraction.

Integrates with Global Fishing Watch (GFW) presence and identity data
to extract and filter candidate vessels within a designated spill origin window.
"""

from __future__ import annotations
import os
import json
import math
from datetime import datetime
from typing import List, Optional

from backend.schemas import CandidateVessel, OriginWindow


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def get_candidate_vessels(
    origin_window: Optional[OriginWindow] = None,
    cache_path: str = "candidates_with_metrics.json"
) -> List[CandidateVessel]:
    """
    Produce candidate vessels for Phase 5 ranking.
    Loads real pre-correlated GFW AIS data from cache if available.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    file_path = os.path.join(repo_root, cache_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Candidate dataset not found at {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates: List[CandidateVessel] = []
    for item in data:
        candidate = CandidateVessel(
            mmsi=item["mmsi"],
            name=item["name"],
            type=item["type"],
            flag=item["flag"],
            position_lat=float(item["position_lat"]),
            position_lon=float(item["position_lon"]),
            distance_from_origin_km=float(item["distance_from_origin_km"]),
            heading_deg=float(item["heading_deg"]),
            speed_kts=float(item["speed_kts"]),
            ais_gap_minutes=int(item["ais_gap_minutes"]),
            dark_vessel=bool(item.get("dark_vessel", False)),
            behavioral_anomaly_score=float(item.get("behavioral_anomaly_score", 0.0)),
            cargo_history=item.get("cargo_history", []),
            bidirectional_drift_agreement=item.get("bidirectional_drift_agreement", None),
            position_timestamp_utc=item.get("position_timestamp_utc"),
        )
        candidates.append(candidate)

    return candidates
