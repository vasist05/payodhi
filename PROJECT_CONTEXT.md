# Payodhi: Automated Marine Oil Spill Detection & Attribution System
## Comprehensive Repository & Architecture Context

---

## 1. Project Overview & System Scope

**Payodhi** is an end-to-end automated platform for marine oil spill detection, false-positive verification, hydrodynamic drift trajectory forecasting, AIS vessel correlation, multi-pillar forensic polluter attribution, and rapid Coast Guard operational response.

### Hackathon / Problem Statement
- **Problem Statement**: SIH-143 / Automated Marine Oil Spill Detection & Attribution.
- **Active Git Branch**: `vasist2`
- **Current Milestone**: Integrated Full-Stack System spanning:
  - **Phase 1**: Sentinel-1 SAR imagery ingestion & deep learning segmentation.
  - **Phase 2**: Multi-modal False-Positive Lookalike Filter (PyTorch ResNet-18 SAR-UV + CSIRO 25-feature Voting Ensemble + Temperature Scaling).
  - **Phase 3**: Forward & backward hydrodynamic oil spill trajectory drift simulation.
  - **Phase 4**: AIS trajectory parsing, vessel history tracking, and dark window identification.
  - **Phase 5**: 7-Pillar Maritime Forensic Attribution Engine (Kinematic CPA, Dark Gaps, Loitering ΔV, Capacity Veto, Waterline Draft Change, 5,000-run Null Permutation Monte Carlo test, ±15% Environmental Sensitivity stress test, Platt calibration, 3-tier legal verdict).
  - **Phase 6**: UNCLOS / MARPOL Annex I compliant Evidence Dossier generation with SHA-256 cryptographic chain of custody.
  - **Phase 8**: Coast Guard Tactical Alert & Interception Engine (Great-circle Haversine routing, 15-station ICG registry, 100 km asset proximity queries, SMSGatewayHub/Fast2SMS dispatch, WebSocket push, React tactical dashboard).

---

## 2. Exhaustive Directory Structure & File Manifest

```
payodhi/
├── .env                                         # Local environment variables & secrets (gitignored)
├── .env.example                                 # Environment variable template with documentation
├── .gitignore                                   # Git ignore rules
├── PROJECT_CONTEXT.md                           # Comprehensive architecture and file manifest (this file)
├── README.md                                    # Top-level repository overview & quickstart
├── README_PHASE8.md                             # Phase 8 Coast Guard Alerting guide & specifications
├── docker-compose.yml                           # Multi-container orchestration (PostGIS/TimescaleDB, Redis, MinIO, Backend)
├── phase_2_files.md                             # Phase 2 ML & Database integration snapshot
├── sih-143-plan.md                              # SIH-143 system design, master plan & milestone tracking
├── sih-final-backend.zip                        # Bundled backend archive
├── tree.txt                                     # Repository tree snapshot
│
├── backend/                                     # Backend Services, Database & Operational APIs
│   ├── Dockerfile                               # CPU-optimized backend Dockerfile (PyTorch wheels caching)
│   ├── alembic.ini                              # Alembic migration configuration
│   ├── requirements.txt                         # Backend Python package dependencies
│   ├── ais_pipeline/                            # AIS stream ingestion and processing pipeline
│   ├── alembic/                                 # Database migration scripts & environment
│   │   ├── README                               # Alembic environment documentation
│   │   ├── env.py                               # Async migration environment setup (asyncpg)
│   │   ├── script.py.mako                       # Alembic migration script template
│   │   └── versions/                            # Versioned database migration files
│   │       ├── df1c2aa7702d_initial_tables.py                  # Baseline schema (Tables 1-8)
│   │       ├── fb8eca0547d6_advanced_triggers_and_timescale.py # Triggers, Hypertables, Hash chaining
│   │       └── c72b10a90df1_align_spill_polygon_index.py       # Spatial GIST index alignment (idx_spills_polygon)
│   ├── api/                                     # Operational & Response REST/WebSocket Service
│   │   ├── main.py                              # FastAPI operational service entrypoint & CORS
│   │   └── response_api.py                      # REST endpoints & /ws/responses WebSocket router
│   ├── app/                                     # Core Application Service (FastAPI REST Engine)
│   │   ├── __init__.py
│   │   ├── main.py                              # FastAPI app entrypoint, lifespan events, CORS, router mounting
│   │   ├── config.py                            # Pydantic Settings (Postgres, TimescaleDB, Redis, MinIO, Model paths)
│   │   ├── db/                                  # Database connection and ORM models
│   │   │   ├── __init__.py
│   │   │   ├── session.py                       # AsyncSessionLocal, async engine, get_session dependency
│   │   │   └── models/                          # SQLAlchemy ORM models (strictly matching DataBaseFinal.md)
│   │   │       ├── __init__.py
│   │   │       ├── ais_gap.py                   # AIS transponder gap tracking model
│   │   │       ├── attribution_score.py         # 7-pillar vessel attribution scoring model
│   │   │       ├── audit_log.py                 # Table 8: audit_log (singular, append-only, SHA-256 hash chaining)
│   │   │       ├── cpa_event.py                 # Table 5: cpa_events (Closest Point of Approach)
│   │   │       ├── dossier.py                   # Evidence dossier and court artifact model
│   │   │       ├── drift_run.py                 # Table 7: drift_runs (Hydrodynamic drift trajectories)
│   │   │       ├── enums.py                     # System Enums (SpillStatusEnum, SceneStatusEnum, VerdictEnum, etc.)
│   │   │       ├── environmental_data.py        # Table 6: environmental_data (Metocean wind, currents, SST)
│   │   │       ├── job.py                       # Asynchronous background job tracker
│   │   │       ├── scene.py                     # Table 3: scenes (wind_speed, wind_direction, footprint polygon)
│   │   │       ├── spill.py                     # Table 4: spills (14 columns, PostGIS MultiPolygon, review_notes)
│   │   │       ├── track.py                     # Table 2: tracks (TimescaleDB hypertable for AIS trajectory points)
│   │   │       └── vessel.py                    # Table 1: vessels (Ship registry, IMO, MMSI, dimensions, DWT)
│   │   ├── repositories/                        # Data Access Layer (Async Repository pattern)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                          # Generic AsyncRepository[T] base interface
│   │   │   ├── audit_repo.py                    # AuditRepository (append-only, SHA-256 continuous hash chaining)
│   │   │   ├── scene_repo.py                    # SceneRepository (CRUD, wind retrieval, spatial queries)
│   │   │   └── spill_repo.py                    # SpillRepository (ST_GeomFromText, selectinload scene context)
│   │   ├── routers/                             # FastAPI HTTP Routers
│   │   │   ├── __init__.py
│   │   │   ├── health.py                        # GET /health (Async health checks: DB, Redis, MinIO)
│   │   │   └── spills.py                        # POST /api/v1/spills/filter, GET /api/v1/spills, GET /api/v1/spills/{id}
│   │   ├── schemas/                             # Pydantic v2 validation & serialization schemas
│   │   │   ├── __init__.py
│   │   │   ├── common.py                        # Spatial GeoJSON <-> WKT conversion utilities
│   │   │   ├── scene.py                         # SceneBase, SceneResponse (dynamic wind_u10/wind_v10 @computed_field)
│   │   │   └── spill.py                         # SpillBase (14 columns), SpillCandidate, SpillFilterBatchRequest/Response
│   │   └── services/                            # Business Logic & Infrastructure Service Layer
│   │       ├── __init__.py
│   │       ├── filter_service.py                # FilterService (3-tier hybrid wind resolution, batch isolation)
│   │       └── storage.py                       # MinIO S3 object storage integration client
│   ├── attribution_engine/                      # Attribution service staging & test harness
│   │   └── tests/                               # Attribution pipeline integration tests
│   ├── evidence_engine/                         # Evidence dossier generator module
│   │   └── tests/                               # Evidence engine tests
│   ├── integration/                             # Inter-module integration tests and fixtures
│   ├── notification/                            # Phase 8 Coast Guard Alerting & Response Engine
│   │   ├── __init__.py
│   │   ├── alerts.db                            # SQLite runtime persistence for alert history and duty acknowledgements
│   │   ├── event_bus.py                         # Async in-memory pub/sub EventBus for WebSocket fan-out
│   │   ├── geo_utils.py                         # Great-circle Haversine math, nearest stations, 100km asset proximity
│   │   ├── response_engine.py                   # 3 Safety Gates, dispatch_response orchestrator, ETA computation
│   │   └── sms_client.py                        # SMSGatewayHub & Fast2SMS client + Indian mobile phone sanitization
│   └── scripts/                                 # Backend utility scripts
│       ├── __init__.py
│       └── test_workflow.py                     # Full end-to-end backend verification script
│
├── config/                                      # Forensic Weights, Calibration & Verdict Configs
│   ├── ahp_weights.yaml                         # Analytic Hierarchy Process (AHP) pairwise matrix & normalized weights
│   ├── calibration.yaml                         # Platt scaling / Isotonic regression calibration coefficients
│   └── verdict_thresholds.yaml                  # 3-Tier legal admissibility criteria & safety gate thresholds
│
├── core/                                        # Shared Core Intelligence & Scientific Engines
│   ├── __init__.py
│   ├── common/                                  # Shared domain utilities and data contracts
│   ├── phase1_sar/                              # Phase 1: Sentinel-1 SAR Ingestion & Segmentation
│   ├── phase2_false_positive/                   # Phase 2: False-Positive Lookalike Filter Engine
│   │   ├── __init__.py
│   │   ├── dataset.py                           # PyTorch Dataset for SAR patches + ERA5 UV components
│   │   ├── evaluate.py                          # Evaluation metrics (ROC-AUC, Precision, Recall, ECE calibration)
│   │   ├── inference.py                         # SpillFilter inference class (PyTorch CNN + CSIRO Voting Classifier)
│   │   ├── model.py                             # ResNet-18 SAR-UV CNN model architecture + Temperature Scaling
│   │   ├── requirements.txt                     # ML dependencies (torch, torchvision, scikit-learn, pillow)
│   │   ├── train.py                             # Training loop with focal loss, validation, temperature calibration
│   │   └── checkpoints/                         # Trained model checkpoints
│   │       ├── best_model_sar_only.pth          # SAR single-channel CNN weights
│   │       ├── best_model_sar_speed.pth         # SAR + Wind Speed 2-channel CNN weights
│   │       ├── best_model_sar_uv.pth            # SAR + Wind U/V 3-channel CNN weights (T = 1.3788)
│   │       └── csiro_classifier.joblib          # 25-feature CSIRO Voting Ensemble (ROC-AUC: 1.0000)
│   ├── phase3_drift/                            # Phase 3: Hydrodynamic Drift & Trajectory Simulation
│   ├── phase4_ais/                              # Phase 4: AIS Track Parsing, Interpolation & Gap Analysis
│   ├── phase5_attribution/                      # Phase 5: 7-Pillar Maritime Forensic Attribution Engine
│   │   ├── __init__.py
│   │   ├── calibration.py                       # Platt scaling & isotonic confidence calibration
│   │   ├── fusion.py                            # Multi-factor AHP weight fusion & capacity veto logic
│   │   ├── pillar1_cpa.py                       # Pillar 1: Nautical Kinematic Intercept (CPA & TCPA)
│   │   ├── pillar2_dark_vessel.py               # Pillar 2: Dark Vessel & AIS Gap Detection
│   │   ├── pillar3_loitering.py                 # Pillar 3: Loitering & Sudden Speed Drop (ΔV)
│   │   ├── pillar4_capacity_veto.py             # Pillar 4: Bonn Agreement Volume vs. Vessel DWT Capacity Veto
│   │   ├── pillar5_draft_change.py              # Pillar 5: Waterline Displacement (Draft Change)
│   │   ├── pillar6_permutation.py               # Pillar 6: 5,000-Run Null Permutation Monte Carlo Test (p-value)
│   │   ├── pillar7_sensitivity.py               # Pillar 7: Weather Sensitivity & Perturbation Stress-Testing
│   │   └── verdict.py                           # 3-Tier Legal Admissibility Verdict Engine
│   └── phase6_dossier/                          # Phase 6: UNCLOS/MARPOL Evidence Dossier & Chain of Custody
│
├── data/                                        # Reference Data, Benchmarks, Inputs & Registries
│   ├── csiro/                                   # CSIRO dataset staging
│   ├── fixtures/                                # Testing mock fixtures and scenarios
│   ├── fp_filter/                               # False-positive filter datasets & ERA5 wind cache
│   │   ├── wind_metadata.json                   # 5,630 CSIRO patches with matched ERA5 (u10, v10) vectors
│   │   ├── csiro_patches/                       # Benchmark SAR image patches (5,630 images)
│   │   │   ├── non_oil/                         # 3,725 Lookalikes (low-wind, algal blooms, biogenic films)
│   │   │   └── oil/                             # 1,905 Confirmed genuine mineral oil spill patches
│   │   └── era5_cache/                          # Cached NetCDF ERA5 oceanic wind grids (15 global regions)
│   │       ├── ADR_2023-05-15.nc                # Adriatic Sea
│   │       ├── BAH_2023-05-15.nc                # Baltic Sea
│   │       ├── EGY_2023-05-15.nc                # Egypt / Red Sea
│   │       ├── GBR_2023-05-15.nc                # North Sea / UK
│   │       ├── GGu_2023-05-15.nc                # Gulf of Guinea
│   │       ├── ISR_2023-05-15.nc                # Eastern Mediterranean
│   │       ├── JAP_2023-05-15.nc                # Sea of Japan
│   │       ├── JAV_2023-05-15.nc                # Java Sea
│   │       ├── LUC_2023-05-15.nc                # Caribbean / St. Lucia
│   │       ├── MAU_2023-05-15.nc                # Mauritania Coast
│   │       ├── NOR_2023-05-15.nc                # Norwegian Sea
│   │       ├── PHI_2023-05-15.nc                # Philippine Sea
│   │       ├── SFr_2023-05-15.nc                # San Francisco Coast
│   │       ├── UNKNOWN_2023-05-15.nc            # Open Ocean fallback
│   │       └── VEN_2023-05-15.nc                # Gulf of Venezuela
│   ├── incidents/                               # Historical ground-truth incident records
│   ├── phase1_input/                            # Raw Sentinel-1 GeoTIFF scenes
│   ├── phase2_input/                            # Candidate spill patch inputs
│   ├── phase4_input/                            # Raw AIS NMEA / CSV tracking streams
│   ├── processed/                               # Output staging for inference runs
│   │   ├── images/                              # Extracted candidate images
│   │   ├── polygons/                            # Vectorized spill polygons
│   │   └── rejected_lookalikes/                 # Flagged false-positive archives
│   └── response/                                # Phase 8 Operational Registries
│       ├── coast_guard_stations.json            # 15 Indian Coast Guard command bases (coords, radii, phone, region)
│       └── interception_vessels.json            # 12 fallback ICG patrol vessels (MMSI, speed, home port)
│
├── docs/                                        # Architectural Documentation, Guides & Benchmarks
│   ├── PROJECT_CONTEXT-phase_2.md               # Historical Phase 2 context snapshot
│   ├── phase2_benchmarks.md                     # Phase 2 ML model benchmarks across ablation variants
│   ├── walkthrough.md                           # Verification logs and integration walkthroughs
│   ├── pitch_deck/                              # System presentation assets & architecture diagrams
│   └── guides/                                  # Deep-dive engineering guides
│       ├── DataBaseFinal.md                     # Ground-truth database contract (Tables 1-8, triggers, invariants)
│       ├── README.md                            # Comprehensive system architecture overview
│       ├── phase5Final.md                       # Complete 7-Pillar Forensic Attribution specification & red flags
│       └── phase6Final.md                       # Evidence Dossier, court reporting & chain of custody specification
│
├── frontend/                                    # Tactical User Interface
│   └── dashboard/                               # React + Vite + TypeScript + TailwindCSS Dashboard
│       ├── index.html                           # Single Page Application HTML host
│       ├── package.json                         # Frontend dependencies (React, Lucide icons, Tailwind, Vite)
│       ├── package-lock.json                    # Locked dependency tree
│       ├── postcss.config.js                    # PostCSS configuration
│       ├── tailwind.config.js                   # TailwindCSS theme tokens & tactical dark palette
│       ├── tsconfig.json                        # TypeScript compiler options
│       ├── tsconfig.node.json                   # Node TypeScript configuration
│       ├── vite.config.ts                       # Vite server with /api and /ws reverse proxies (:8000)
│       └── src/                                 # Frontend source code
│           ├── App.tsx                          # Tactical command UI: Preset demo triggers, live alert card, history
│           ├── index.css                        # Design system, glassmorphism tokens & animations
│           ├── main.tsx                         # React 18 DOM mount entrypoint
│           ├── vite-env.d.ts                    # Vite client types declaration
│           ├── api/                             # API clients and HTTP wrappers
│           ├── components/                      # UI components
│           │   └── CoastGuardAlertPanel.tsx     # High-contrast tactical alert card with ETA & 1-click Ack
│           ├── data/                            # Static UI references & mock scenarios
│           ├── hooks/                           # Custom React hooks
│           │   └── useResponses.ts              # WebSocket live stream hook with auto-reconnect & REST history
│           ├── pages/                           # Screen views
│           ├── services/                        # Client service layer
│           └── types/                           # TypeScript interfaces
│               └── index.ts                     # CoastGuardAlert, InterceptionVessel, Station, Incident contracts
│
├── models/                                      # Legacy Model Scripts (Rebased to core/)
│   ├── __init__.py
│   ├── common/                                  # Common candidate schema definitions
│   │   ├── __init__.py
│   │   └── schema.py                            # Candidate spill data structures
│   ├── detection/                               # Detection model checkpoints
│   ├── drift_model/                             # Legacy drift models
│   │   └── outputs/                             # Trajectory outputs
│   ├── false_positive/                          # Legacy false-positive filter placeholder
│   ├── false_positive_filter/                   # Standalone legacy filter module
│   │   ├── __init__.py
│   │   ├── dataset.py                           # Dataset loader
│   │   ├── evaluate.py                          # Metric evaluator
│   │   ├── inference.py                         # Inference engine
│   │   ├── model.py                             # CNN architecture
│   │   ├── requirements.txt                     # Dependencies
│   │   ├── train.py                             # Training script
│   │   └── checkpoints/                         # Model weights
│   │       ├── best_model_sar_only.pth
│   │       ├── best_model_sar_speed.pth
│   │       ├── best_model_sar_uv.pth
│   │       └── csiro_classifier.joblib
│   └── sar_segmentation/                        # SAR U-Net / DeepLab segmentation weights
│
├── scripts/                                     # Data Engineering & Evaluation Utilities
│   ├── join_era5_metadata.py                    # Match Sentinel-1 patches with ERA5 NetCDF wind vectors
│   ├── run_ablation_study.py                    # Multi-mode ablation benchmark (sar_only vs sar_speed vs sar_uv)
│   └── show_tree.py                             # Formatted repository tree visualizer
│
└── tests/                                       # Automated Test Suites & Regression Harness
    ├── test_phase2_db_integration.py            # Phase 2 ↔ DB contracts (GeoJSON/WKT, schemas, 3-tier wind math)
    ├── integration/                             # End-to-end multi-phase integration tests
    └── unit/                                    # Forensic Attribution Unit Tests
        ├── test_calibration.py                  # Platt scaling / Isotonic calibration verification
        ├── test_fusion.py                       # AHP fusion & capacity veto tests
        ├── test_pillar1_cpa.py                  # Pillar 1 Geodesic CPA / TCPA math tests
        ├── test_pillar2_dark_vessel.py          # Pillar 2 AIS gap & silence window detection tests
        ├── test_pillar3_loitering.py            # Pillar 3 Speed drop & loitering analysis tests
        ├── test_pillar4_capacity_veto.py        # Pillar 4 Bonn volume vs DWT veto tests
        ├── test_pillar5_draft_change.py         # Pillar 5 Waterline draft reduction tests
        ├── test_pillar6_permutation.py          # Pillar 6 5,000-run Monte Carlo permutation p-value tests
        ├── test_pillar7_sensitivity.py          # Pillar 7 ±15% weather perturbation stability tests
        └── test_verdict.py                      # 3-tier legal verdict threshold & H0 tests
```

---

## 3. Database Architecture & Ground Truth (`docs/guides/DataBaseFinal.md`)

### The Golden Rule
> **Do not use `Base.metadata.create_all()`.** All database tables, spatial indexes, triggers, and hypertables are strictly managed through Alembic migrations (`backend/alembic/versions/`).

### Database Table Manifest

| Table | Model Class | Name | Role & Invariants |
|---|---|---|---|
| **Table 1** | `Vessel` | `vessels` | Ship registry (MMSI, IMO, callsign, vessel_type, length, beam, DWT, draft). |
| **Table 2** | `Track` | `tracks` | AIS trajectory points (TimescaleDB hypertable partitioned on `timestamp`, spatial `location` geometry). |
| **Table 3** | `Scene` | `scenes` | SAR imagery metadata (`wind_speed`, `wind_direction`, `footprint` polygon, `storage_uri`). |
| **Table 4** | `Spill` | `spills` | **The ONLY writable surface for Phase 2.** Exactly 14 columns. PostGIS MultiPolygon. |
| **Table 5** | `CPAEvent` | `cpa_events` | Closest Point of Approach calculations between vessels and spill polygons. |
| **Table 6** | `EnvironmentalData` | `environmental_data` | Metocean data (ocean currents, waves, SST, ERA5 wind grid). |
| **Table 7** | `DriftRun` | `drift_runs` | Forward and backward hydrodynamic drift trajectories (OpenDrift format). |
| **Table 8** | `AuditLog` | `audit_log` | **Singular table name `audit_log`**. Append-only with cryptographic SHA-256 continuous hash chaining. |

### Auxiliary Operational Models
- `AisGap`: AIS transponder blackout tracking (start time, end time, duration, bounding box).
- `AttributionScore`: Detailed 7-pillar forensic breakdown per candidate vessel.
- `Dossier`: UNCLOS-ready evidence packages stamped with root SHA-256 hash.
- `Job`: Background job tracker for long-running drift simulations and batch inferences.

### Exact Column Specification for `spills` (Table 4)
1. `id`: `UUID PK` (server default `gen_random_uuid()`)
2. `scene_id`: `UUID NOT NULL FK → scenes(id)`
3. `detected_at`: `timestamptz NOT NULL DEFAULT now()`
4. `spill_polygon`: `geometry(MultiPolygon,4326) NOT NULL`
5. `area_sq_km`: `numeric(10,3) NOT NULL CHECK > 0`
6. `detection_model_name`: `text NOT NULL`
7. `detection_model_version`: `text NOT NULL`
8. `confidence_score`: `numeric(4,3) NOT NULL CHECK 0–1`
9. `processing_run_id`: `UUID NULL`
10. `status`: `spill_status_enum NOT NULL DEFAULT 'detected'` (`detected`, `under_review`, `confirmed`, `rejected`)
11. `reviewed_by`: `text NULL`
12. `review_notes`: `text NULL` (stores all model explanations, lookalike flags, and operator notes)
13. `created_at`: `timestamptz NOT NULL DEFAULT now()`
14. `updated_at`: `timestamptz NOT NULL DEFAULT now()`

> **Zero Banned Columns**: Absolutely NO `wind_u10`, `wind_v10`, `wind_speed`, or `rejection_reason` columns exist on `spills`.
>
> **Wind Provenance**: Wind data lives exclusively on `scenes`. $U_{10}$ and $V_{10}$ are dynamically computed on read via:
> $$u_{10} = \text{wind\_speed} \cdot \sin(\text{radians}(\text{wind\_direction}))$$
> $$v_{10} = \text{wind\_speed} \cdot \cos(\text{radians}(\text{wind\_direction}))$$

---

## 4. Scientific & Machine Learning Architecture

### Phase 2: False-Positive Lookalike Filter (`core/phase2_false_positive/`)
- **Backbone**: Multimodal PyTorch `ResNet-18` accepting:
  - `sar_only`: 1-channel SAR amplitude.
  - `sar_speed`: 2-channel SAR + scalar wind speed grid.
  - `sar_uv`: 3-channel SAR + directional $U_{10}$ and $V_{10}$ wind vectors.
- **Calibration**: Post-hoc Temperature Scaling ($T = 1.3788$) for calibrated probabilities (ECE $\le 0.05$).
- **Tabular Ensemble**: 25 physical backscatter, damping, texture, gradient, and contrast features evaluated by a `HistGradientBoosting` + `ExtraTrees` Voting Classifier trained on 5,630 CSIRO SAR patches (ROC-AUC: 1.0000).
- **3-Tier Hybrid Wind Resolution in `FilterService`**:
  1. `scene_derived`: Derives $(u_{10}, v_{10})$ from `scenes.wind_speed` and `scenes.wind_direction`.
  2. `metadata_json`: Looks up exact historical ERA5 vector for benchmark patches from `data/fp_filter/wind_metadata.json`.
  3. `none`: Neutral fallback `(None, None)`.

### Phase 5: 7-Pillar Maritime Forensic Attribution Engine (`core/phase5_attribution/`)
- **Pillar 1 (`pillar1_cpa.py`)**: Nautical Kinematic Intercept using geodesic distance (`pyproj.Geod`) to find minimum CPA distance (km) and TCPA (hours) between vessel AIS and backward-drift trajectory.
- **Pillar 2 (`pillar2_dark_vessel.py`)**: Detects deliberate transponder shutoffs (>10 min gaps in open water >5 nm from coast) with spatial proximity penalty to spill origin.
- **Pillar 3 (`pillar3_loitering.py`)**: Detects operational loitering and sudden speed drops (>50% drop to <5 knots for >30 min) in open water outside designated ports/anchorages.
- **Pillar 4 (`pillar4_capacity_veto.py`)**: Bonn Agreement Volume Estimation ($V = \text{Area} \times \text{Thickness}$). Zeroes out score (Veto = True) if vessel DWT/bilge capacity cannot physically produce the slick.
- **Pillar 5 (`pillar5_draft_change.py`)**: Waterline displacement tracking from static AIS voyage history ($\Delta \text{draft} \ge 0.5\text{ m}$).
- **Pillar 6 (`pillar6_permutation.py`)**: 5,000-iteration Monte Carlo null permutation test calculating empirical statistical significance ($p < 0.001$).
- **Pillar 7 (`pillar7_sensitivity.py`)**: Environmental perturbation stress testing (100 runs under $\pm 15\%$ wind speed, $\pm 10^\circ$ current direction) yielding Environmental Stability Index ($\ge 90\%$).
- **Calibration (`calibration.py`)**: Converts raw composite AHP scores into true statistical probabilities via Platt scaling / Isotonic regression.
- **Verdict Engine (`verdict.py`)**: 3-Tier legal admissibility output:
  - **Tier 1: PROSECUTABLE** ($p < 0.01$, Score $\ge 80$, Stability $\ge 90\%$).
  - **Tier 2: PERSON OF INTEREST** ($p < 0.05$, Score $60\text{--}79$).
  - **Tier 3: INSUFFICIENT EVIDENCE** (H₀ Null hypothesis retained to prevent false accusations).

### Phase 8: Coast Guard Alert & Operational Response Engine (`backend/notification/`)
- **3 Safety Gates**:
  1. `is_verified_oil == True` (suppresses unverified anomalies).
  2. `filter_confidence >= 0.75` (ensures high detection certainty).
  3. `30-minute cooldown` per station (prevents alert spamming during ongoing incidents).
- **Proximity & Routing (`geo_utils.py`)**: Great-circle Haversine distance to 15 Indian Coast Guard bases (`data/response/coast_guard_stations.json`), identifying primary and backup command centers.
- **Interception Fleet Estimation**: Queries patrol vessels within 100 km and computes intercept ETA at 18-knot cruising speed.
- **Persistence & Dispatch**: Persists to SQLite (`backend/notification/alerts.db`), fans out over `EventBus` to WebSocket clients, and dispatches SMS alerts via SMSGatewayHub or Fast2SMS.

---

## 5. Configuration & Calibration Subsystem (`config/`)

1. **`config/ahp_weights.yaml`**:
   - Analytic Hierarchy Process pairwise comparison matrix across spatial proximity, kinematic CPA, AIS silence gaps, loitering, and draft change.
   - Consistent weights ensuring mathematical defensibility in legal proceedings.
2. **`config/calibration.yaml`**:
   - Platt scaling sigmoid parameters ($A, B$) and Isotonic regression binning parameters.
3. **`config/verdict_thresholds.yaml`**:
   - Strictly defined thresholds for `PROSECUTABLE`, `PERSON_OF_INTEREST`, and `INSUFFICIENT_EVIDENCE`.

---

## 6. API Layer & Service Endpoints

### 1. Main Application Engine (`backend/app/main.py`) — Port 8000
- `GET /health`: Asynchronous health checks across PostgreSQL, Redis, and MinIO S3.
- `POST /api/v1/spills/filter`: Batch false-positive filtering endpoint with strict transaction isolation and pinned response models (`confirmed`, `rejected`, `failed`, `model_mode`, `calibration_temperature`).
- `GET /api/v1/spills`: Query confirmed and detected spills with eager-loaded scene wind context.
- `GET /api/v1/spills/{id}`: Detailed single-spill retrieval.

### 2. Operational Response Engine (`backend/api/main.py`) — Port 8000
- `WS /ws/responses`: Live WebSocket stream pushing real-time tactical alerts to connected duty dashboards.
- `GET /api/responses`: Fetch complete alert history from SQLite (newest first).
- `POST /api/responses/{id}/ack`: Duty officer one-click acknowledgement endpoint.
- `POST /api/responses/test`: Trigger end-to-end test alerts through safety gates and dispatch pipeline.
- `GET /api/stations`: Retrieve 15-station Indian Coast Guard command registry.
- `POST /api/interception-nearby`: Query interception assets within radius $R$ km of coordinate $(lat, lon)$.

---

## 7. Tactical Frontend Dashboard (`frontend/dashboard/`)

- **Tech Stack**: React 18, TypeScript, Vite, TailwindCSS, Lucide React icons.
- **Components**:
  - `CoastGuardAlertPanel.tsx`: High-contrast tactical alert card showing assigned station, distance, intercept ETA, available patrol fleet, and instant acknowledgement action.
  - `App.tsx`: Real-time incident triggers (Ennore / Chennai, Mumbai High, Paradip Port, Kochi Coast), live WebSocket alert monitor, and historical audit table.
- **Data Flow**: `useResponses.ts` hook manages resilient WebSocket streaming with automated exponential backoff reconnects and REST history hydration.

---

## 8. Verification Suites & Test Coverage

1. **Phase 2 Contract & DB Tests (`tests/test_phase2_db_integration.py`)**:
   - `test_geojson_wkt_conversion`: Passed (WKT MultiPolygon conversion).
   - `test_scene_derived_wind_components`: Passed ($U_{10}/V_{10}$ math).
   - `test_spill_table_contract_and_no_banned_columns`: Passed (Zero banned columns, exactly 14 allowed fields).
   - `test_pinned_batch_response_shape`: Passed (Response model validation).
   - `test_filter_service_hybrid_wind_resolution`: Passed (All 3 resolution tiers tested).
2. **Phase 5 Forensic Attribution Unit Tests (`tests/unit/`)**:
   - `test_pillar1_cpa.py`: CPA/TCPA time-aligned geodesic calculation.
   - `test_pillar2_dark_vessel.py`: Open-water AIS blackout window detection.
   - `test_pillar3_loitering.py`: Sudden speed drop and operational loitering.
   - `test_pillar4_capacity_veto.py`: Bonn volume formula & DWT capacity veto.
   - `test_pillar5_draft_change.py`: Waterline displacement verification.
   - `test_pillar6_permutation.py`: Monte Carlo baseline shuffle & empirical p-value.
   - `test_pillar7_sensitivity.py`: Wind/current perturbation stress tests.
   - `test_calibration.py`: Platt & Isotonic probability calibration.
   - `test_fusion.py`: AHP weighted combination & veto zeroing.
   - `test_verdict.py`: 3-tier classification & null hypothesis retention.
3. **Phase 8 Tactical Response Verification**:
   - Clean startup, WebSocket broadcast fan-out, 3-gate safety evaluation, SQLite persistence, and SMS payload generation.
