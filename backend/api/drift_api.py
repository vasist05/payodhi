"""
Drift API — Integration point for Phase 6 dashboard.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from models.drift_model.drift_sim import DriftSimulator

_simulator = None

def get_simulator():
    global _simulator
    if _simulator is None:
        _simulator = DriftSimulator(project_root=str(project_root))
    return _simulator

def run_drift_pipeline(spill_id="latest"):
    """Run the complete drift pipeline."""
    sim = get_simulator()
    return sim.run_pipeline()

def get_heatmap_path():
    """Get path to heatmap image."""
    sim = get_simulator()
    return sim.output_dir / "heatmap.png"

def get_vessel_ranking():
    """Get proximity-ranked vessel list."""
    sim = get_simulator()
    sim.load_phase1_data()
    sim.load_phase2_data()
    sim.load_phase4_data()
    return sim.calculate_vessel_scores()

def get_attribution_leaderboard():
    """Get Phase 5 Multi-Factor Attribution Leaderboard."""
    sim = get_simulator()
    results = sim.run_pipeline()
    attr = results.get("attribution", {})
    return attr.get("leaderboard", [])

def get_evidence_report():
    """Get Phase 6 Legal Explainability Evidence Report."""
    sim = get_simulator()
    results = sim.run_pipeline()
    attr = results.get("attribution", {})
    return attr.get("evidence_report", {})

def get_simulation_results():
    """Get latest simulation results JSON."""
    sim = get_simulator()
    results_path = sim.output_dir / "results.json"
    if results_path.exists():
        import json
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def run_end_to_end_attribution(incident_id="INC-ENNORE-2017-0128"):
    """
    Complete end-to-end pipeline:
    Phase 1 (Detection) + Phase 2 (Filter) + Phase 3 (Drift) +
    Phase 4 (AIS Correlate) + Phase 5 (Ranking) + Phase 6 (Evidence Report).
    """
    sim = get_simulator()
    return sim.run_pipeline()

def import_phase1_scene(scene_path: str, scene_meta: dict):
    """Bridge a Phase 1 SAR scene detection directly into Phase 3 input and run simulation."""
    from backend.integration.phase1_to_phase3 import Phase1ToPhase3Bridge
    bridge = Phase1ToPhase3Bridge()
    output_path = bridge.export_to_phase3_input(scene_path, scene_meta)
    sim = get_simulator()
    return sim.run_pipeline()

def import_phase2_scene(scene_path: str, scene_meta: dict = None, wind_uv: tuple = (-3.5, -4.2)):
    """Bridge Phase 1 Detection -> Phase 2 False-Positive Filter -> Phase 3 Drift Simulation."""
    from backend.integration.pipeline_p1_p2_p3 import IntegratedSpillPipeline
    pipeline = IntegratedSpillPipeline()
    p2_path = pipeline.export_to_phase2_input(
        scene_path=scene_path,
        scene_meta=scene_meta,
        wind_uv=wind_uv
    )
    sim = get_simulator()
    return sim.run_pipeline()


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 60)
    print("🧪 TESTING DRIFT API WITH INTEGRATED PHASE 1 & 2 OUTPUT")
    print("=" * 60)
    
    # 1. Test pipeline
    results = run_drift_pipeline()
    meta = results.get("metadata", {})
    print(f"✅ Pipeline executed. Spill ID: {results.get('spill_id')}")
    print(f"   Centroid: {results.get('centroid')}")
    print(f"   Phase 2 Verified: {meta.get('is_verified_oil')}, Filter Conf: {meta.get('filter_confidence')}")
    print(f"   Wind Vector: u={meta.get('wind_u10')} m/s, v={meta.get('wind_v10')} m/s")
    
    # 2. Test heatmap path
    hm_path = get_heatmap_path()
    print(f"✅ Heatmap exists: {hm_path.exists()} -> {hm_path}")
    
    # 3. Test vessel ranking
    ranking = get_vessel_ranking()
    print(f"✅ Top vessel: {ranking[0]['vessel_id']} with score {ranking[0]['agreement_score']}")
    print("=" * 60)
