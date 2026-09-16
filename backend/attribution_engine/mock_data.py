"""
backend/attribution_engine/mock_data.py
=======================================
Mock inputs for Phase 5 & 6 (Haldia and Mumbai incidents).

Haldia scenario (get_mock_inputs):
    4 candidate vessels, Haldia Port entrance, Bay of Bengal, July 2018.
    One clear winner (MV SAGAR SAMRAT), two mid-range, one clear loser.

Mumbai scenario (get_mumbai_mock_inputs):
    4 candidates, Mumbai Offshore, Arabian Sea, August 2020.
    Includes a dark (SAR-only) vessel contact alongside a tanker.

For the live Ennore incident, real GFW AIS data is used via:
    backend/ais_pipeline/correlate.py → candidates_with_metrics.json
"""

from backend.schemas import (
    DriftResult, OriginWindow, HeatmapPoint,
    CandidateVessel
)
from typing import Tuple, List


def get_mock_drift_result() -> DriftResult:
    """
    Mock Phase 3 output: backward drift from a spill detected at
    Haldia port entrance, Bay of Bengal, July 2018.
    """
    return DriftResult(
        spill_detected_utc="2018-07-12T14:32:00Z",
        spill_centroid_lat=21.98,
        spill_centroid_lon=88.10,
        origin_window=OriginWindow(
            start_utc="2018-07-12T14:05:00Z",
            end_utc="2018-07-12T14:25:00Z",
            region_km_radius=4.5
        ),
        origin_heatmap=[
            HeatmapPoint(lat=21.97, lon=88.09, weight=0.88),
            HeatmapPoint(lat=21.96, lon=88.10, weight=0.74),
            HeatmapPoint(lat=21.98, lon=88.11, weight=0.61),
            HeatmapPoint(lat=21.95, lon=88.08, weight=0.43),
            HeatmapPoint(lat=22.01, lon=88.12, weight=0.22),
        ]
    )


def get_mock_candidate_vessels() -> List[CandidateVessel]:
    """
    Mock Phase 4 output: 4 candidate vessels found in the origin
    region/time window. Designed so:

      Vessel A (MMSI 419001234) — clear winner: close, tanker, anomalous AIS, high drift agreement
      Vessel B (MMSI 538007891) — mid-range: tanker but wrong direction, some gap
      Vessel C (MMSI 477123456) — mid-range: bulk carrier, farther, no AIS gap
      Vessel D (MMSI 636012345) — clear loser: 18 km away, bulk carrier, normal behavior
    """
    return [
        CandidateVessel(
            mmsi="419001234",
            name="MV SAGAR SAMRAT",
            type="Oil tanker",
            flag="IN",
            position_lat=21.965,
            position_lon=88.085,
            distance_from_origin_km=2.8,
            heading_deg=215,
            speed_kts=5.8,
            ais_gap_minutes=22,           # 22-min gap during critical window → suspicious
            dark_vessel=False,
            behavioral_anomaly_score=78.0,
            cargo_history=["crude oil", "fuel oil", "HSD"],
            bidirectional_drift_agreement=0.91
        ),
        CandidateVessel(
            mmsi="538007891",
            name="MV PACIFIC GLORY",
            type="Chemical/oil tanker",
            flag="MH",
            position_lat=21.940,
            position_lon=88.120,
            distance_from_origin_km=5.6,
            heading_deg=45,               # heading away from spill origin — inconsistent
            speed_kts=9.1,
            ais_gap_minutes=0,
            dark_vessel=False,
            behavioral_anomaly_score=41.0,
            cargo_history=["chemical", "palm oil"],
            bidirectional_drift_agreement=0.54
        ),
        CandidateVessel(
            mmsi="477123456",
            name="MV HAI YANG",
            type="Bulk carrier",
            flag="HK",
            position_lat=21.920,
            position_lon=88.075,
            distance_from_origin_km=8.1,
            heading_deg=190,
            speed_kts=7.4,
            ais_gap_minutes=0,
            dark_vessel=False,
            behavioral_anomaly_score=18.0,
            cargo_history=["iron ore", "coal"],
            bidirectional_drift_agreement=0.38
        ),
        CandidateVessel(
            mmsi="636012345",
            name="MV ATLANTIC BRIDGE",
            type="General cargo",
            flag="LR",
            position_lat=21.830,
            position_lon=87.970,
            distance_from_origin_km=18.4,
            heading_deg=310,
            speed_kts=11.2,
            ais_gap_minutes=0,
            dark_vessel=False,
            behavioral_anomaly_score=9.0,
            cargo_history=["general cargo"],
            bidirectional_drift_agreement=0.12
        ),
    ]


def get_mock_inputs() -> Tuple[DriftResult, List[CandidateVessel]]:
    """Convenience function — returns (drift_result, vessel_list)."""
    return get_mock_drift_result(), get_mock_candidate_vessels()


def get_mumbai_mock_inputs() -> Tuple[DriftResult, List[CandidateVessel]]:
    """Mock Phase 3 & 4 data for an offshore Mumbai High incident with dark vessel presence."""
    drift = DriftResult(
        spill_detected_utc="2020-08-14T06:15:00Z",
        spill_centroid_lat=18.95,
        spill_centroid_lon=72.75,
        origin_window=OriginWindow(
            start_utc="2020-08-14T04:30:00Z",
            end_utc="2020-08-14T06:00:00Z",
            region_km_radius=5.0
        ),
        origin_heatmap=[]
    )
    vessels = [
        CandidateVessel(
            mmsi="419008888",
            name="MT MAHARASHTRA",
            type="Crude Oil Tanker",
            flag="IN",
            position_lat=18.96,
            position_lon=72.73,
            distance_from_origin_km=2.4,
            heading_deg=165.0,
            speed_kts=4.2,
            ais_gap_minutes=45,
            dark_vessel=False,
            behavioral_anomaly_score=85.0,
            cargo_history=["Crude Oil", "Heavy Fuel Oil"],
            bidirectional_drift_agreement=0.94,
            position_timestamp_utc="2020-08-14T05:10:00Z"
        ),
        CandidateVessel(
            mmsi="354112233",
            name="UNKNOWN (Dark SAR Contact)",
            type="Unknown",
            flag="Unknown",
            position_lat=18.97,
            position_lon=72.72,
            distance_from_origin_km=3.8,
            heading_deg=170.0,
            speed_kts=6.0,
            ais_gap_minutes=180,
            dark_vessel=True,
            behavioral_anomaly_score=92.0,
            cargo_history=[],
            bidirectional_drift_agreement=0.88,
            position_timestamp_utc="2020-08-14T05:00:00Z"
        ),
        CandidateVessel(
            mmsi="419001999",
            name="MV ARABIAN SEA",
            type="Bulk Carrier",
            flag="IN",
            position_lat=18.91,
            position_lon=72.82,
            distance_from_origin_km=8.6,
            heading_deg=220.0,
            speed_kts=11.5,
            ais_gap_minutes=0,
            dark_vessel=False,
            behavioral_anomaly_score=10.0,
            cargo_history=["Coal"],
            bidirectional_drift_agreement=0.35,
            position_timestamp_utc="2020-08-14T05:30:00Z"
        ),
        CandidateVessel(
            mmsi="636099111",
            name="MV KONKAN TRADER",
            type="General Cargo",
            flag="LR",
            position_lat=18.84,
            position_lon=72.88,
            distance_from_origin_km=18.2,
            heading_deg=340.0,
            speed_kts=13.0,
            ais_gap_minutes=0,
            dark_vessel=False,
            behavioral_anomaly_score=0.0,
            cargo_history=["Steel"],
            bidirectional_drift_agreement=0.10,
            position_timestamp_utc="2020-08-14T05:45:00Z"
        )
    ]
    return drift, vessels


def get_ennore_mock_inputs() -> Tuple[DriftResult, List[CandidateVessel]]:
    """Historical baseline validation case: Ennore 2017 tanker collision."""
    drift = DriftResult(
        spill_detected_utc="2017-01-28T00:00:00Z",
        spill_centroid_lat=13.230,
        spill_centroid_lon=80.330,
        origin_window=OriginWindow(
            start_utc="2017-01-27T18:00:00Z",
            end_utc="2017-01-28T02:00:00Z",
            region_km_radius=4.0
        ),
        origin_heatmap=[
            HeatmapPoint(lat=13.254, lon=80.351, weight=0.96),
            HeatmapPoint(lat=13.258, lon=80.347, weight=0.82),
            HeatmapPoint(lat=13.249, lon=80.355, weight=0.70),
        ]
    )
    vessels = [
        CandidateVessel(
            mmsi="419000988",
            name="DAWN KANCHIPURAM",
            type="Oil Products Tanker",
            flag="IN",
            position_lat=13.254,
            position_lon=80.351,
            distance_from_origin_km=0.6,
            heading_deg=220.0,
            speed_kts=4.2,
            ais_gap_minutes=90,
            dark_vessel=False,
            behavioral_anomaly_score=94.0,
            cargo_history=["Heavy Fuel Oil", "Bunker Oil"],
            bidirectional_drift_agreement=0.96,
            position_timestamp_utc="2017-01-27T22:30:00Z"
        ),
        CandidateVessel(
            mmsi="235101303",
            name="BW MAPLE",
            type="LPG Tanker",
            flag="GB",
            position_lat=13.248,
            position_lon=80.362,
            distance_from_origin_km=1.8,
            heading_deg=45.0,
            speed_kts=8.5,
            ais_gap_minutes=15,
            dark_vessel=False,
            behavioral_anomaly_score=45.0,
            cargo_history=["Liquefied Petroleum Gas"],
            bidirectional_drift_agreement=0.65,
            position_timestamp_utc="2017-01-27T22:30:00Z"
        ),
        CandidateVessel(
            mmsi="419000222",
            name="MV COROMANDEL CARRIER",
            type="Bulk Carrier",
            flag="IN",
            position_lat=13.210,
            position_lon=80.390,
            distance_from_origin_km=7.5,
            heading_deg=180.0,
            speed_kts=12.0,
            ais_gap_minutes=0,
            dark_vessel=False,
            behavioral_anomaly_score=10.0,
            cargo_history=["Thermal Coal"],
            bidirectional_drift_agreement=0.25,
            position_timestamp_utc="2017-01-27T23:00:00Z"
        ),
        CandidateVessel(
            mmsi="419000555",
            name="TUG ENNORE 1",
            type="Tug / Support",
            flag="IN",
            position_lat=13.265,
            position_lon=80.315,
            distance_from_origin_km=14.2,
            heading_deg=90.0,
            speed_kts=6.0,
            ais_gap_minutes=0,
            dark_vessel=False,
            behavioral_anomaly_score=5.0,
            cargo_history=["Port Towing"],
            bidirectional_drift_agreement=0.08,
            position_timestamp_utc="2017-01-27T23:15:00Z"
        )
    ]
    return drift, vessels

