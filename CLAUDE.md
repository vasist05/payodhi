# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚀 Development Commands

### Backend Operations
- **Run the full forensic pipeline (Phases 1-6):** `python backend/integration/pipeline_p1_to_p6.py`
- **Start the FastAPI server:** `python run_backend.py` or `python backend/api/main.py`
- **Access API docs:** http://127.0.0.1:8000/docs (when server is running)
- **Run attribution tests:** `python -m pytest backend/attribution_engine/tests/`
- **Run evidence tests:** `python -m pytest backend/evidence_engine/tests/`

### Frontend Operations  
- **Start the dashboard:** `cd frontend/dashboard && npm run dev` (opens http://localhost:5173)
- **Install frontend deps:** `cd frontend/dashboard && npm install`

### Setup & Installation
- **Backend setup:** 
  ```bash
  python -m venv venv
  # Windows: .\venv\Scripts\activate
  # Linux/macOS: source venv/bin/activate
  pip install -r requirements.txt
  ```
- **Frontend setup:** `cd frontend/dashboard && npm install`

### Data & Models
- **Sample data location:** `data/processed/images/` (for SAR imagery testing)
- **Model artifacts:** Stored in respective model directories under `models/`
- **Pipeline outputs:** `models/drift_model/outputs/` (JSON reports, heatmaps)

## 🏗️ Code Architecture

### End-to-End Pipeline (7 Phases)
The system processes satellite imagery through a sequential forensic workflow:

1. **Phase 1 - Detection** (`models/detection/`): 
   - U-Net with ResNet-34 encoder for SAR oil spill segmentation
   - Input: Sentinel-1 SAR imagery → Output: GeoJSON polygons of candidate spills

2. **Phase 2 - Filtering** (`models/false_positive_filter/`):
   - SpillFilterNet (multi-channel CNN) + CSIRO ensemble classifier
   - Uses ERA5 wind data to reject biogenic lookalikes
   - Output: Verified oil spill candidates

3. **Phase 3 - Drift Simulation** (`models/drift_model/`):
   - Lagrangian particle backtracking (OpenDrift/GNOME principles)
   - Gaussian KDE for origin probability mapping
   - Output: Drift trajectories + origin heatmap

4. **Phase 4 - AIS Correlation** (`backend/ais_pipeline/`):
   - Historical AIS trajectory analysis (AISHub/GFW)
   - Spatiotemporal querying + dark ship detection
   - Output: Correlated vessel candidates

5. **Phase 5 - Attribution Ranking** (`backend/attribution_engine/`):
   - Bayesian weighted scoring (drift:35%, time:25%, distance:20%, vessel:10%, anomaly:10%)
   - Output: Ranked suspect vessels with scores (0-100)

6. **Phase 6 - Evidence Generation** (`backend/evidence_engine/`):
   - Explainable AI (XAI) legal dossier creator
   - Generates corroborating/exculpatory factors + chain-of-custody
   - Output: Court-ready audit report (JSON/printable)

7. **Phase 7 - Dashboard** (`frontend/dashboard/`):
   - React 18 + Vite + TypeScript + Tailwind CSS
   - Leaflet maritime map with slick/vessel overlays
   - Real-time telemetry + evidence dossier viewer

### Key Structural Patterns
- **Dependency Injection:** Core components initialized in pipeline orchestrator (`FullForensicPipeline`)
- **Data Contracts:** Shared Pydantic schemas in `backend/schemas.py` (GeoJSON, vessel models)
- **Synthetic Data:** AIS generation in pipeline for demo/testing when real data unavailable
- **Modular Phases:** Each phase implements clean interfaces for testing/isolation
- **Configurable Paths:** Pipeline uses `project_root` detection for portability

### Important Files & Entry Points
- `backend/integration/pipeline_p1_to_p6.py` - Main pipeline orchestrator
- `backend/run_backend.py` - FastAPI server launcher
- `backend/api/main.py` - API endpoint definitions
- `models/detection/inference.py` - Phase 1 model inference
- `models/false_positive_filter/inference.py` - Phase 2 filtering logic
- `models/drift_model/drift_sim.py` - Phase 3 drift simulation
- `backend/attribution_engine/ranking.py` - Phase 5 Bayesian scoring
- `backend/evidence_engine/evidence_builder.py` - Phase 6 XAI report generation

### Development Guidelines
- **Phase Independence:** Each phase can be tested separately with mock inputs
- **Schema Validation:** All inter-phase data uses Pydantic models from `schemas.py`
- **Error Handling:** Pipeline gracefully handles missing data (generates synthetic AIS)
- **Logging:** Progress tracked via phase-separated console output with visual separators
- **Output Format:** Final results saved as JSON with standardized structure for API consumption