"""
tests/test_phase123_integration.py

Comprehensive test suite verifying the end-to-end integration of:
- Phase 1 (SAR Oil Spill Detection)
- Phase 2 (SAR-UV False-Positive Filter)
- Phase 3 (Hydrodynamic Backward Drift Simulation & Origin Estimation)
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Setup sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend"))

import numpy as np
from app.db.models.enums import DriftStatusEnum
from app.schemas.drift import (
    CandidateScoreResponse,
    ConfidenceContour,
    DriftRunRequest,
    DriftRunResponse,
    ForwardAttributionCandidateRequest,
    ForwardAttributionRequest,
    ForwardAttributionResponse,
    HeatmapSummary,
    OriginEstimate,
)
from app.schemas.pipeline import IntegratedPipelineRequest, IntegratedPipelineResponse
from app.schemas.spill import SpillCandidate, SpillResponse
from app.services.drift_service import DriftService, _compute_fingerprint
from app.services.pipeline_service import IntegratedPipelineService
from core.phase3_drift.drift_model.aggregate import (
    build_heatmap,
    confidence_contours,
    contour_to_polygon,
    peak_location,
)
from core.phase3_drift.drift_model.forcing import make_synthetic_current, make_synthetic_wind
from core.phase3_drift.drift_model.runner import run_backward, run_forward
from core.phase3_drift.drift_model.sampler import sample_scenarios
from core.phase3_drift.forward_attribution.rank import classify_attribution, rank_candidates
from core.phase3_drift.forward_attribution.scorer import score_vessel


class TestPhase3PhysicsAndDrift(unittest.TestCase):
    """Test core physics, forcing generation, sampling, and trajectory solvers."""

    def test_synthetic_forcing_creation(self):
        wind_path = "data/forcing/test_wind.nc"
        curr_path = "data/forcing/test_curr.nc"
        w = make_synthetic_wind(wind_path)
        c = make_synthetic_current(curr_path)
        self.assertTrue(os.path.exists(w))
        self.assertTrue(os.path.exists(c))

    def test_scenario_sampler(self):
        det_time = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
        scenarios = sample_scenarios(
            det_lon=72.5,
            det_lat=21.0,
            det_time=det_time,
            window_hours=12,
            n=10,
            seed=42,
        )
        self.assertEqual(len(scenarios), 10)
        for s in scenarios:
            self.assertEqual(s["detection_lon"], 72.5)
            self.assertEqual(s["detection_lat"], 21.0)
            self.assertLessEqual(s["release_time"], det_time)
            self.assertIn("oil_type", s)

    def test_backward_drift_runner(self):
        scenario = {
            "detection_lon": 72.5,
            "detection_lat": 21.0,
            "detection_time": datetime(2024, 6, 15, 12, 0),
            "release_time": datetime(2024, 6, 15, 6, 0),
            "oil_type": "GENERIC MEDIUM CRUDE",
        }
        wind_path = "data/forcing/test_wind.nc"
        curr_path = "data/forcing/test_curr.nc"
        out_nc = run_backward(
            scenario=scenario,
            wind=wind_path,
            current=curr_path,
            outdir="data/test_ensemble_out",
            n=50,
        )
        self.assertTrue(os.path.exists(out_nc))

    def test_heatmap_and_contour_aggregation(self):
        # Run 2 scenarios
        scenarios = sample_scenarios(72.5, 21.0, datetime(2024, 6, 15, 12, 0), window_hours=6, n=2)
        nc_files = [
            run_backward(
                scenarios[0],
                "data/forcing/test_wind.nc",
                "data/forcing/test_curr.nc",
                outdir="data/test_ensemble_out",
                n=30,
            ),
            run_backward(
                scenarios[1],
                "data/forcing/test_wind.nc",
                "data/forcing/test_curr.nc",
                outdir="data/test_ensemble_out",
                n=30,
            ),
        ]
        H, lon_bins, lat_bins = build_heatmap(nc_files, (71.0, 74.0), (19.5, 22.5), resolution=0.1)
        self.assertEqual(H.shape, (len(lat_bins) - 1, len(lon_bins) - 1))
        self.assertAlmostEqual(float(H.sum()), 1.0, places=3)

        peak = peak_location(H, lon_bins, lat_bins)
        self.assertIn("lon", peak)
        self.assertIn("lat", peak)
        self.assertIn("prob", peak)

        contours = confidence_contours(H, levels=(0.5, 0.75, 0.9))
        for lvl in (0.5, 0.75, 0.9):
            self.assertIn(lvl, contours)
            poly = contour_to_polygon(contours[lvl], lon_bins, lat_bins)
            self.assertIsInstance(poly, list)

    def test_forward_vessel_scoring(self):
        cand = {
            "mmsi": "419000123",
            "vessel_name": "MT TEST TANKER",
            "lon": 72.4,
            "lat": 20.95,
            "release_time": datetime(2024, 6, 15, 6, 0),
            "detection_time": datetime(2024, 6, 15, 12, 0),
            "oil_type": "GENERIC MEDIUM CRUDE",
        }
        res = score_vessel(
            cand,
            detection_lon=72.5,
            detection_lat=21.0,
            wind="data/forcing/test_wind.nc",
            current="data/forcing/test_curr.nc",
            outdir="data/test_fwd_out",
            threshold_km=50.0,
        )
        self.assertIn("forward_score", res)
        self.assertGreaterEqual(res["forward_score"], 0.0)
        self.assertLessEqual(res["forward_score"], 1.0)


class TestDriftServiceAndPipelines(unittest.IsolatedAsyncioTestCase):
    """Test DriftService and IntegratedPipelineService with mock DB session."""

    async def asyncSetUp(self):
        self.mock_session = AsyncMock()
        self.scene_id = uuid4()
        self.spill_id = uuid4()

        # Mock scene
        self.mock_scene = MagicMock()
        self.mock_scene.id = self.scene_id
        self.mock_scene.captured_at = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
        self.mock_scene.wind_speed = 7.5
        self.mock_scene.wind_direction = 120.0
        self.mock_scene.storage_uri = "data/fixtures/sample_scene.png"

        # Mock spill
        now = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
        self.mock_spill = MagicMock()
        self.mock_spill.id = self.spill_id
        self.mock_spill.scene_id = self.scene_id
        self.mock_spill.detected_at = now
        self.mock_spill.created_at = now
        self.mock_spill.updated_at = now
        self.mock_spill.area_sq_km = 3.45
        self.mock_spill.confidence_score = 0.92
        self.mock_spill.status = "confirmed"
        self.mock_spill.detection_model_name = "SAR_Unet_Detector"
        self.mock_spill.detection_model_version = "resnet34-v1.0"
        self.mock_spill.processing_run_id = None
        self.mock_spill.reviewed_by = None
        self.mock_spill.review_notes = None
        self.mock_spill.spill_polygon = {"type": "MultiPolygon", "coordinates": [[[[72.5, 21.0], [72.51, 21.0], [72.51, 21.01], [72.5, 21.01], [72.5, 21.0]]]]}
        self.mock_spill.scene = None

    async def test_drift_service_backward_reconstruction(self):
        svc = DriftService(self.mock_session)
        svc.scenes.get_by_id = AsyncMock(return_value=self.mock_scene)
        svc.spills.get_by_id = AsyncMock(return_value=self.mock_spill)
        svc.drift_repo.get_by_fingerprint = AsyncMock(return_value=None)

        mock_drift_run = MagicMock()
        mock_drift_run.id = uuid4()
        mock_drift_run.status = DriftStatusEnum.running
        svc.drift_repo.create_drift_run = AsyncMock(return_value=mock_drift_run)
        svc.drift_repo.update_status = AsyncMock()
        svc.audit.append = AsyncMock()

        res = await svc.run_backward_reconstruction(
            scene_id=self.scene_id,
            spill_id=self.spill_id,
            detection_lon=72.5,
            detection_lat=21.0,
            detection_time=self.mock_scene.captured_at,
            window_hours=6,
            n_scenarios=10,
        )

        self.assertEqual(res["status"], "completed")
        self.assertIsNotNone(res["origin_estimate"])
        self.assertGreater(len(res["contours"]), 0)
        self.assertIsNotNone(res["heatmap_summary"])
        self.assertEqual(res["heatmap_summary"].total_runs, 10)

    async def test_drift_service_forward_attribution(self):
        svc = DriftService(self.mock_session)
        candidates = [
            ForwardAttributionCandidateRequest(
                mmsi="419000111",
                vessel_name="TANKER ALPHA",
                vessel_lon=72.48,
                vessel_lat=20.98,
                release_time=datetime(2024, 6, 15, 8, 0, tzinfo=timezone.utc),
            ),
            ForwardAttributionCandidateRequest(
                mmsi="419000222",
                vessel_name="CARGO BETA",
                vessel_lon=70.0,
                vessel_lat=18.0,
                release_time=datetime(2024, 6, 15, 8, 0, tzinfo=timezone.utc),
            ),
        ]

        res = await svc.score_candidate_vessels(
            scene_id=self.scene_id,
            spill_id=self.spill_id,
            detection_lon=72.5,
            detection_lat=21.0,
            detection_time=self.mock_scene.captured_at,
            candidates=candidates,
        )

        self.assertEqual(len(res.ranked_candidates), 2)
        # First candidate closer should have higher score
        self.assertGreater(res.ranked_candidates[0].forward_score, res.ranked_candidates[1].forward_score)

    async def test_integrated_pipeline_service(self):
        pipeline_svc = IntegratedPipelineService(self.mock_session)

        # Mock detection service output
        sample_cand = SpillCandidate(
            patch_path="data/phase1_crops/sample_patch.png",
            center_lat=21.0,
            center_lon=72.5,
            scene_id=self.scene_id,
            spill_polygon={"type": "Polygon", "coordinates": [[[72.5, 21.0], [72.51, 21.0], [72.51, 21.01], [72.5, 21.01], [72.5, 21.0]]]},
            area_sq_km=2.5,
            detection_confidence=0.88,
        )
        pipeline_svc.detection_svc.run_detection = AsyncMock(
            return_value={
                "scene_id": self.scene_id,
                "spill_count": 1,
                "spills": [self.mock_spill],
                "candidates": [sample_cand],
                "status": "success",
                "message": "Detected 1 spill",
            }
        )

        # Mock Phase 2 filter output
        pipeline_svc.filter_svc_sar_uv.filter_batch = AsyncMock(
            return_value={
                "confirmed": [self.mock_spill],
                "rejected": [],
                "failed": [],
                "model_mode": "sar_uv",
                "calibration_temperature": 1.0,
            }
        )

        # Mock Phase 3 drift output
        mock_origin = OriginEstimate(
            peak_lon=72.45,
            peak_lat=20.95,
            peak_prob=0.15,
            release_window_start=datetime(2024, 6, 15, 0, 0, tzinfo=timezone.utc),
            release_window_end=datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc),
        )
        mock_heatmap = HeatmapSummary(
            lon_min=71.0,
            lon_max=74.0,
            lat_min=19.5,
            lat_max=22.5,
            resolution_deg=0.02,
            grid_shape=[150, 150],
            total_runs=20,
            successful_runs=20,
        )
        pipeline_svc.drift_svc.run_backward_reconstruction = AsyncMock(
            return_value={
                "run_id": uuid4(),
                "scene_id": self.scene_id,
                "spill_id": self.spill_id,
                "status": "completed",
                "run_fingerprint": "a" * 64,
                "origin_estimate": mock_origin,
                "contours": [
                    ConfidenceContour(
                        level=0.9,
                        geometry={"type": "Polygon", "coordinates": [[[72.4, 20.9], [72.5, 20.9], [72.5, 21.0], [72.4, 21.0], [72.4, 20.9]]]},
                    )
                ],
                "heatmap_summary": mock_heatmap,
                "output_storage_uri": "minio://payodi-drift-runs/summary.json",
                "execution_time_ms": 120.5,
                "message": "Drift completed",
            }
        )

        response = await pipeline_svc.execute_full_pipeline(
            scene_id=self.scene_id,
            image_path="data/fixtures/sample_scene.png",
            detection_threshold=0.50,
            min_pixels=50,
            filter_mode="sar_uv",
            drift_window_hours=12,
            n_drift_scenarios=20,
        )

        self.assertEqual(response.status, "success")
        self.assertEqual(response.spill_count_detected, 1)
        self.assertEqual(response.spill_count_confirmed, 1)
        self.assertEqual(response.spill_count_rejected, 0)
        self.assertEqual(len(response.drift_reconstructions), 1)
        self.assertIsNotNone(response.drift_reconstructions[0].origin_estimate)


if __name__ == "__main__":
    unittest.main()
