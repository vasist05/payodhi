from dataclasses import dataclass
from datetime import datetime


@dataclass
class DriftScenario:
    detection_lon: float
    detection_lat: float
    detection_time: datetime
    release_time: datetime
    oil_type: str
    mode: str = "backward"

    @property
    def duration_hours(self) -> float:
        return (self.detection_time - self.release_time).total_seconds() / 3600.0