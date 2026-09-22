"""
Shared Data Schema for Oil Spill Detection & Attribution Pipeline.
Provides standardized data contracts between Phase 1 (Detection), Phase 2 (False-Positive Filter),
and Phase 3 (Drift Modeling).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class SpillCandidate:
    """
    Standardized interface for a proposed oil spill candidate.
    Phase 1 generates this candidate list.
    Phase 2 filters and enriches it with verification and wind context.
    Phase 3 uses verified candidates for backward/bidirectional drift reconstruction.
    """
    id: str
    patch_path: str                             # Path to 256x256 or 400x400 patch image
    center_lat: float = 0.0                     # Approximate / exact latitude
    center_lon: float = 0.0                     # Approximate / exact longitude
    timestamp: Optional[datetime] = None        # Acquisition timestamp
    detection_confidence: float = 1.0           # Confidence score from Phase 1 U-Net (0.0 to 1.0)
    bbox: Tuple[int, int, int, int] = (0, 0, 400, 400) # (x1, y1, x2, y2) in full scene
    is_verified_oil: Optional[bool] = None      # Populated by Phase 2 filter (True = Oil, False = Lookalike)
    filter_confidence: Optional[float] = None   # Confidence score from Phase 2 classifier
    wind_u10: Optional[float] = None            # 10m eastward wind component (m/s)
    wind_v10: Optional[float] = None            # 10m northward wind component (m/s)
    scene_sigma0_db: Optional[float] = None      # Open-water σ⁰ reference for the source scene (dB)
    radiometric_span_db: Optional[float] = None  # Patch contrast span, p98-p2 (dB)
    radiometric_anomaly: Optional[bool] = None   # True if scene sits far from -17.4 dB baseline
    wind_speed: Optional[float] = None          # Wind speed magnitude (m/s)
    wind_direction: Optional[float] = None      # Meteorological wind direction (degrees)
    rejection_reason: Optional[str] = None      # Explanation if rejected (e.g., lookalike low wind / biogenic)
    source: Optional[str] = None                # Wind source: "ERA5", "Regional", "None"
    contour_points: Optional[List[Tuple[float, float]]] = None # List of (lat, lon) or pixel contour points
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpillPolygon:
    """
    Output format for Phase 3 integration.
    Exported to JSON for drift simulation (GNOME / OpenDrift backward & forward modeling).
    """
    polygon: List[Tuple[float, float]]  # List of (lat, lon) points forming the spill boundary
    timestamp: datetime                  # Acquisition timestamp (when SAR was imaged)
    centroid: Optional[Tuple[float, float]] = None  # (lat, lon) center point
    confidence: float = 0.0              # Final combined / filtered confidence
    id: str = ""                         # Unique ID for tracking
    scene_id: str = ""                   # Source scene ID
    is_verified_oil: bool = True         # Filter status
    filter_confidence: Optional[float] = None
    wind_u10: Optional[float] = None
    wind_v10: Optional[float] = None
    scene_sigma0_db: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    rejection_reason: Optional[str] = None
    source: Optional[str] = None

    def to_json(self) -> dict:
        """Convert to standard JSON dictionary."""
        return {
            "id": self.id,
            "scene_id": self.scene_id,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            "centroid": [self.centroid[0], self.centroid[1]] if self.centroid else None,
            "confidence": round(float(self.confidence), 4),
            "is_verified_oil": self.is_verified_oil,
            "filter_confidence": round(float(self.filter_confidence), 4) if self.filter_confidence is not None else None,
            "wind_u10": self.wind_u10,
            "wind_v10": self.wind_v10,
            "scene_sigma0_db": self.scene_sigma0_db,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "rejection_reason": self.rejection_reason,
            "source": self.source,
            "polygon": [[float(lat), float(lon)] for lat, lon in self.polygon],
        }

    @classmethod
    def from_json(cls, data: dict):
        """Reconstruct from JSON dictionary."""
        ts_raw = data["timestamp"]
        if isinstance(ts_raw, str):
            ts = datetime.fromisoformat(ts_raw)
        else:
            ts = ts_raw

        return cls(
            id=data.get("id", ""),
            scene_id=data.get("scene_id", ""),
            timestamp=ts,
            centroid=tuple(data["centroid"]) if data.get("centroid") else None,
            confidence=data.get("confidence", 0.0),
            is_verified_oil=data.get("is_verified_oil", True),
            filter_confidence=data.get("filter_confidence"),
            wind_u10=data.get("wind_u10"),
            wind_v10=data.get("wind_v10"),
            scene_sigma0_db=data.get("scene_sigma0_db"),
            wind_speed=data.get("wind_speed"),
            wind_direction=data.get("wind_direction"),
            rejection_reason=data.get("rejection_reason"),
            source=data.get("source"),
            polygon=[(p[0], p[1]) for p in data.get("polygon", [])],
        )
