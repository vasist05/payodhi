# 🌊 SIH26143 — Marine Oil Spill Tracking & Vessel Attribution Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C.svg)](https://pytorch.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC.svg)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **One-Line Summary:**  
> Python and PyTorch power our AI models — a U-Net CNN for detection, a multi-channel CNN and ensemble classifier for lookalike rejection, custom physics code for hydrodynamic drift backtracking, and Bayesian multi-factor logic for vessel attribution — backed by open satellite (Sentinel-1 SAR), meteorological wind (ERA5), and ship-tracking (AIS) data, with a court-ready XAI legal evidence engine and an interactive React/Vite dashboard on top.

---

## 📌 Table of Contents
- [Executive Overview](#-executive-overview)
- [End-to-End Pipeline Architecture](#-end-to-end-pipeline-architecture)
- [Technology Stack](#-technology-stack)
- [Datasets & Remote Sensing Sources](#-datasets--remote-sensing-sources)
- [Project Directory Structure](#-project-directory-structure)
- [Installation & Setup](#-installation--setup)
- [Running the System](#-running-the-system)
- [API Reference](#-api-reference)
- [Legal Evidence & Explainable AI (XAI)](#-legal-evidence--explainable-ai-xai)

---

## 🛰️ Executive Overview

Marine oil pollution inflicts catastrophic ecological and economic damage. Traditional satellite monitoring is often hindered by high false-alarm rates (caused by low winds, biogenic slicks, and algae) and a lack of autonomous linkage between detected slicks and the commercial vessels responsible.

**SIH26143** provides an autonomous, end-to-end forensic pipeline that:
1. **Detects** dark slick formations in Synthetic Aperture Radar (SAR) imagery.
2. **Rejects** false-positive lookalikes using fused satellite backscatter and atmospheric wind fields.
3. **Backtracks** oil slicks to their exact spatiotemporal discharge origin via Lagrangian drift modeling.
4. **Correlates** historical Automatic Identification System (AIS) vessel trajectories.
5. **Ranks** suspect vessels using multi-factor Bayesian probabilistic scoring.
6. **Compiles** legally defensible, explainable audit dossiers with complete chain-of-custody tracking for maritime law enforcement agencies (e.g., Indian Coast Guard, NTRO).

---

## 🔄 End-to-End Pipeline Architecture

```
                                  [ Sentinel-1 SAR Image ]
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │  PHASE 1: SAR Oil Spill Segmentation         │
                      │  • PyTorch U-Net with ResNet-34 Encoder      │
                      │  • Pixel-level Mask -> GeoJSON Polygons      │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │  PHASE 2: False Positive & Lookalike Filter  │
                      │  • SpillFilterNet (Multi-Channel ResNet CNN) │
                      │  • CSIRO Gradient Boosting/ExtraTrees        │
                      │  • ERA5 Atmospheric Wind Vector Ingestion    │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │  PHASE 3: Backward Drift & Origin Simulation │
                      │  • Lagrangian Leeway Particle Backtracking   │
                      │  • NOAA GNOME / OpenDrift Methodology        │
                      │  • Gaussian Kernel Density Estimation (KDE)  │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │  PHASE 4: Spatiotemporal AIS Correlation     │
                      │  • AISHub / GFW Trajectory Slicing           │
                      │  • Bounding-Box & Route Interpolation        │
                      │  • Dark Ship & Gap Detection                 │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │  PHASE 5: Multi-Criteria Suspect Ranking     │
                      │  • Weighted Bayesian Scoring (0 - 100)       │
                      │  • Drift, Time, Distance, Ship Risk, Anomaly │
                      │  • Verdict: STRONG / INCONCLUSIVE / LOW      │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │  PHASE 6: XAI Legal Evidence Dossier Engine  │
                      │  • Plain-English Justification Bullets       │
                      │  • Corroborating / Exculpatory Analysis      │
                      │  • Printable Court-Ready Audit Report        │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │  PHASE 7: Interactive Maritime Dashboard     │
                      │  • React 18 + Vite + TypeScript + Tailwind   │
                      │  • Leaflet Nautical Mapping & Slick Vectors  │
                      │  • Time-Machine Playback & Live Scene Ingest │
                      └──────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

### 🐍 Core Language & Environment
* **Python 3.10+** — Core language powering all AI, computer vision, drift simulation, and backend logic.
* **venv / virtualenv** — Virtual environment management isolating dependencies across team members.

### 🧠 Deep Learning & Image Segmentation (Phase 1)
* **PyTorch & Torchvision** — Core deep learning framework for model definition, tensor manipulation, and GPU/CPU inference.
* **U-Net Architecture** — Dual-convolution encoder-decoder with skip connections specialized for precise pixel-level semantic segmentation of SAR oil slicks.
* **ResNet-34 Encoder** — Feature extractor initialized with ImageNet pre-trained weights for accelerated pattern and edge convergence.
* **Dice Loss + Binary Cross-Entropy (BCE)** — Combined loss function addressing heavy class imbalance between dark ocean backgrounds and narrow spill contours.
* **Adam Optimizer** — Adaptive learning rate optimizer applied during network convergence.

### 🧪 False-Positive Rejection & Lookalike Filter (Phase 2)
* **SpillFilterNet (Multi-Channel CNN)** — Modified ResNet-18/34 taking 3-channel stacked inputs: SAR backscatter amplitude + ERA5 eastward wind ($u_{10}$) + northward wind ($v_{10}$) to distinguish true crude slicks from biogenic lookalikes.
* **CSIRO Ensemble Classifier (`csiro_classifier.joblib`)** — Soft-voting ensemble combining `HistGradientBoostingClassifier` and `ExtraTreesClassifier` (150 estimators) operating on 25 statistical, gradient, and texture features.
* **Scikit-Learn & Joblib** — Model evaluation, stratified k-fold cross-validation, and serialized model artifact management.

### 🖼️ Image & Geospatial Data Handling
* **rasterio** — Reading and georeferencing multi-band satellite formats (GeoTIFF / JP2).
* **OpenCV (`cv2`) & Pillow (PIL)** — Patch tiling, boundary contouring, geometric resizing, and morphology operations.
* **NumPy & SciPy** — High-performance multidimensional matrix operations and 2D `gaussian_kde` spatial density modeling.
* **Matplotlib** — Headless visualization (`Agg` backend), spatial verification plotting, and color-coded vector diagrams.

### 🌊 Hydrodynamic Drift Simulation (Phase 3)
* **OpenDrift / NOAA GNOME Principles** — Lagrangian particle dispersion modeling simulating surface slick advection.
* **Leeway Drift Physics** — Wind drag coefficient physics ($\approx 3\%$ surface wind factor) combined with ocean surface currents.
* **Gaussian KDE Origin Surface** — Probabilistic 2D heatmapping to pinpoint the highest-likelihood discharge coordinate window ($T - 12\text{h}$ to $T$).

### 🚢 AIS Tracking & Spatiotemporal Correlation (Phase 4)
* **AIS Trajectory Analysis** — Ingestion and interpolation of historical Automatic Identification System records (AISHub / Global Fishing Watch).
* **Kinematic Correlation** — Spatiotemporal query bounding matching vessel tracks against the drift-estimated discharge timestamp and origin polygon.
* **Dark Ship Detection** — Detection of transmitter dropouts, speed anomalies, and loitering maneuvers within territorial waters / EEZs.

### ⚖️ Multi-Factor Attribution & XAI Evidence (Phases 5 & 6)
* **Bayesian Weighted Scoring Formula:**
  $$\text{Score} = 0.35 \times S_{\text{drift}} + 0.25 \times S_{\text{time}} + 0.20 \times S_{\text{distance}} + 0.10 \times S_{\text{vessel}} + 0.10 \times S_{\text{anomaly}}$$
* **Explainable AI (XAI)** — Generates human-readable evidence cards, highlighting corroborating indicators (✅) and disqualifying factors (❌).

### 🌐 Backend, APIs & Dashboard (Phase 7)
* **FastAPI** — High-performance, asynchronous REST API with auto-generated OpenAPI documentation.
* **Uvicorn** — Production ASGI web server.
* **Pydantic v2** — Strict data validation and GeoJSON schema enforcement.
* **React 18.3 & TypeScript** — Frontend UI with strict type safety.
* **Vite 6.1** — Ultra-fast frontend development server and bundling engine.
* **Tailwind CSS 3.4** — Modern utility-first styling with dark-mode aesthetic.
* **Leaflet & React-Leaflet** — Interactive maritime navigation maps rendering satellite overlays, drift trajectories, vessel routes, and slick polygons.
* **Recharts & Lucide React** — Real-time telemetry analytics and maritime iconography.

### 🔧 Infrastructure & Version Control
* **Git & GitHub** — Branch-based collaboration, semantic versioning, and code review.

---

## 📊 Datasets & Remote Sensing Sources

| Category | Source / Dataset | Description |
| :--- | :--- | :--- |
| **SAR Imagery** | **Sentinel-1 SAR** (Copernicus Open Access Hub) | Level-1 Ground Range Detected (GRD) C-band radar backscatter imagery invariant to cloud cover and daylight. |
| **Labeled Spills** | **Zenodo Sentinel-1 SAR Oil Spill Dataset** | Expert-annotated pixel masks classifying crude spills, lookalikes, ships, and clean sea. |
| **Benchmark SAR** | **Deep-SAR SOS Dataset** (Kaggle) | Multi-satellite high-resolution SAR training patches. |
| **Lookalike Benchmark** | **CSIRO Lookalike Dataset** | 5,630 verified oil and non-oil marine patches for false-positive classifier training. |
| **Atmospheric Wind** | **ECMWF ERA5 Reanalysis** (`cdsapi`) | Hourly 10m $U$ and $V$ wind vector components for leeway modeling. |
| **Ocean Currents** | **HYCOM / Copernicus Marine Service** | Sea surface velocity fields for hydrodynamic drift advection. |
| **Vessel Traffic** | **AISHub / Global Fishing Watch (GFW)** | Historical terrestrial and satellite AIS vessel broadcasts (MMSI, speed, heading, draught, ship type). |

---

## 📂 Project Directory Structure

```
sih/
├── backend/
│   ├── ais_pipeline/              # Phase 4: AIS correlation & dark ship identification
│   ├── api/
│   │   ├── adapter.py             # Multi-port real incident datasets (Ennore, Mumbai, etc.)
│   │   ├── drift_api.py           # Drift simulation & KDE heatmap endpoints
│   │   └── main.py                # Primary FastAPI application
│   ├── attribution_engine/        # Phase 5: Multi-factor Bayesian ranking engine
│   ├── evidence_engine/           # Phase 6: XAI legal audit dossier generator
│   ├── integration/
│   │   └── pipeline_p1_to_p6.py   # Unified end-to-end execution pipeline
│   └── schemas.py                 # Shared Pydantic data & GeoJSON contracts
├── data/
│   ├── fp_filter/                 # CSIRO lookalike patches & wind metadata
│   ├── phase1_input/              # SAR incident inputs & test scenes
│   ├── processed/images/          # Optical & SAR satellite test assets
│   └── raw/ais/                   # GFW historical AIS feeds
├── documentation/                 # Technical walkthroughs, test plans & benchmarks
├── frontend/
│   └── dashboard/                 # React 18 + Vite + TypeScript + Tailwind UI
│       ├── src/
│       │   ├── components/        # Map, telemetry, suspect cards & report modals
│       │   └── services/          # API integration clients
│       └── package.json
├── models/
│   ├── common/                    # Shared geospatial schemas & coordinate helpers
│   ├── detection/                 # Phase 1: PyTorch U-Net architecture & inference
│   ├── drift_model/               # Phase 3: Lagrangian leeway simulation & KDE
│   └── false_positive_filter/     # Phase 2: SpillFilterNet CNN & CSIRO ensemble
├── project_scripts/               # Dataset tiling, Kaggle processing & training
├── scripts/                       # Model training & verification scripts
├── requirements.txt               # Backend Python dependencies
├── run_backend.py                 # FastAPI server launcher script
└── README.md                      # Project documentation
```

---

## ⚡ Installation & Setup

### Prerequisites
* **Python:** Version 3.10 or higher
* **Node.js:** Version 18 or higher (with npm)
* **Git:** Installed and configured

### 1. Clone the Repository
```bash
git clone https://github.com/your-org/sih.git
cd sih
```

### 2. Set Up the Python Backend
```bash
# Create and activate virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate

# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Up the React Dashboard
```bash
cd frontend/dashboard
npm install
cd ../..
```

---

## 🚀 Running the System

### Option A: Run the End-to-End Forensic Pipeline (CLI)
Execute the complete multi-phase pipeline (Phase 1 $\rightarrow$ Phase 6) on an incident:
```bash
python backend/integration/pipeline_p1_to_p6.py
```
*Outputs: Segmentation masks, verified candidate status, backward drift vectors, correlated vessels, ranked suspect scores, and the generated legal evidence dossier.*

### Option B: Launch the Interactive Full-Stack Platform

**Step 1: Start the FastAPI Backend Server**
```bash
python run_backend.py
```
* The API will start at: `http://127.0.0.1:8000`
* Interactive Swagger Docs: `http://127.0.0.1:8000/docs`

**Step 2: Start the Vite React Dashboard**
In a separate terminal:
```bash
cd frontend/dashboard
npm run dev
```
* Open your browser at: `http://localhost:5173`

---

## 📡 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | System health check and module status. |
| `GET` | `/api/incidents` | List all tracked spill incidents across Indian maritime zones. |
| `GET` | `/api/incidents/{id}` | Retrieve comprehensive forensic details for a specific incident. |
| `POST`| `/api/incidents/ingest` | Ingest new SAR/optical satellite imagery or coordinate feeds. |
| `GET` | `/api/attribution/{id}` | Fetch Phase 5 suspect vessel rankings and scores. |
| `GET` | `/api/evidence/{id}` | Export Phase 6 court-ready XAI legal audit report. |
| `GET` | `/api/drift/{id}` | Retrieve backward drift trajectories and origin KDE grid. |

---

## ⚖️ Legal Evidence & Explainable AI (XAI)

For maritime enforcement authorities (e.g., Coast Guard, Port Authorities, NTRO), black-box AI scores are insufficient for legal prosecution under MARPOL Annex I. 

SIH26143 incorporates an **Explainable AI (XAI)** audit generator that builds court-ready dossiers:
* **Positive Corroboration:** Identifies spatio-temporal intersection, drift vector alignments, and high-risk cargo types.
* **Exculpatory Evidence:** Explicitly articulates why competing vessels were ruled out (e.g., passing downstream of drift plume, steady cruising speed).
* **Integrity & Chain of Custody:** Captures cryptographic checksums, satellite acquisition timestamps, and weather reanalysis IDs to withstand evidentiary scrutiny.

---

## 👥 Contributors & Acknowledgments
Built with ❤️ for the **Smart India Hackathon (SIH)**.  
Special thanks to Copernicus (ESA), ECMWF, and Global Fishing Watch for providing open earth observation and maritime telemetry data.