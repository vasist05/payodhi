"""
backend/run_attribution.py
===========================
End-to-end runner: Phase 5 (ranking) → Phase 6 (evidence).

Usage
-----
  # Run with mock data (default — for development):
  python -m backend.run_attribution

  # Run with real Phase 4 data (once Phase 4 is ready):
  python -m backend.run_attribution --real

  # Get JSON output (for Phase 7 / dashboard integration):
  python -m backend.run_attribution --json

Integration note for Phase 7 owner (Person 6)
----------------------------------------------
Import the Python function directly for the dashboard backend:

    from backend.run_attribution import run_full_pipeline
    from backend.schemas import EvidenceReport
    import json

    report: EvidenceReport = run_full_pipeline(use_real_data=False)
    # serialize for API response:
    # report_dict = dataclasses.asdict(report)

OR expose via FastAPI (add to backend/api/main.py):

    @app.post("/rank")
    def rank_endpoint():
        report = run_full_pipeline(use_real_data=False)
        return dataclasses.asdict(report)
"""

from __future__ import annotations
import argparse
import json
import dataclasses
from typing import Tuple, List

from backend.schemas import DriftResult, CandidateVessel, EvidenceReport, AttributionOutcome


def _load_mock_data() -> Tuple[DriftResult, List[CandidateVessel]]:
    """Load mock Phase 3 + Phase 4 data."""
    from backend.attribution_engine.mock_data import get_mock_inputs
    return get_mock_inputs()


def _load_real_data() -> Tuple[DriftResult, List[CandidateVessel]]:
    """
    Load real Phase 3 + Phase 4 data for the Ennore 2017 spill.
    """
    from backend.schemas import OriginWindow
    from backend.ais_pipeline.correlate import get_candidate_vessels

    drift = DriftResult(
        spill_detected_utc="2017-01-28T00:00:00Z",
        spill_centroid_lat=13.23,
        spill_centroid_lon=80.33,
        origin_window=OriginWindow(
            start_utc="2017-01-27T20:00:00Z",
            end_utc="2017-01-28T04:00:00Z",
            region_km_radius=5.0,
        ),
        origin_heatmap=[],
    )

    vessels = get_candidate_vessels(drift.origin_window)
    return drift, vessels


def run_full_pipeline(
    use_real_data: bool = False,
    incident_id: str = "INC-HALDIA-2018-0712"
) -> EvidenceReport:
    """
    Full Phase 5 → Phase 6 pipeline.

    Parameters
    ----------
    use_real_data : bool
        If True, calls real Phase 3/4 modules. If False, uses mock data.
    incident_id : str
        Identifier for the spill event.

    Returns
    -------
    EvidenceReport
        Complete evidence report ready for Phase 7 consumption.
    """
    from backend.attribution_engine.ranking import rank_vessels
    from backend.evidence_engine.evidence_builder import build_evidence_report

    if use_real_data:
        drift, candidates = _load_real_data()
    else:
        drift, candidates = _load_mock_data()

    ranked_results, outcome = rank_vessels(candidates, drift)
    report = build_evidence_report(ranked_results, outcome, drift, incident_id)

    return report


def _print_report(report: EvidenceReport) -> None:
    """Pretty-print the report to stdout for verification."""
    divider = "═" * 70

    print(f"\n{divider}")
    print(f"  SIH26143 — OIL SPILL ATTRIBUTION REPORT")
    print(f"  Incident: {report.incident_id}")
    print(f"  Spill Detected: {report.spill_detected_utc}")
    print(f"  Candidates Evaluated: {report.total_candidates_evaluated}")
    print(f"  Overall Outcome: {report.overall_outcome.value}")
    print(f"{divider}\n")

    print(f"SUMMARY: {report.primary_summary}\n")

    for card in report.cards:
        rank_icon = "🥇" if card.rank == 1 else f"#{card.rank}"
        print(f"{rank_icon}  {card.vessel_name}  (MMSI: {card.mmsi})")
        print(f"   Attribution Score: {card.attribution_score:.1f}/100  [{card.outcome_label}]")
        print(f"   {card.narrative}")
        print()
        for b in card.bullets:
            icon = "  ✅" if b.positive else "  ❌"
            print(f"{icon} {b.text}")
        print()
        print(f"   [{card.disclaimer}]")
        print(f"   {'─' * 60}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SIH26143 Attribution Engine — Phase 5 & 6 runner"
    )
    parser.add_argument(
        "--real", action="store_true",
        help="Use real Phase 3/4 data instead of mock data"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output full report as JSON (for API / dashboard use)"
    )
    parser.add_argument(
        "--incident", type=str, default="INC-HALDIA-2018-0712",
        help="Incident identifier"
    )
    args = parser.parse_args()

    report = run_full_pipeline(use_real_data=args.real, incident_id=args.incident)

    if args.json:
        print(json.dumps(dataclasses.asdict(report), indent=2))
    else:
        _print_report(report)
