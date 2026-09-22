# Payodhi: Automated Marine Oil Spill Detection & Attribution System
## Comprehensive Repository & Architecture Context (Branch: `vasist2`)

---

## 1. Project Overview & Context

**Payodhi** is an end-to-end automated platform for marine oil spill detection, verification, trajectory forecasting, and polluter vessel attribution using Sentinel-1 SAR imagery, ERA5 oceanic wind vectors, AIS tracking data, and hydrodynamic modeling.

### Hackathon / Challenge Context
- **Problem Statement**: SIH-143 / Automated Marine Oil Spill Detection & Attribution.
- **Active Git Branch**: `vasist2`
- **Current Milestone**: Phase 2 False-Positive Filtering ↔ PostgreSQL/TimescaleDB Database & FastAPI Backend Integration (Completed and Verified).

---

## 2. Directory Structure & File Manifest

```
payodhi/
├── backend/                              # FastAPI REST Backend & Database Engine
│   ├── Dockerfile                        # CPU-optimized Docker image (PyTorch wheel caching)
│   ├── requirements.txt                  # Backend Python dependencies
│   ├── alembic.ini                       # Alembic database migration configuration
│   ├── alembic/                          # Database migration scripts
│   │   ├── env.py                        # Migration environment setup (asyncpg)
│   │   ├── script.py.mako                # Migration template
│   │   └── versions/                     # Versioned migration files
│   │       ├── df1c2aa7702d_initial_tables.py             # Baseline schema (Tables 1-8)
│   │       ├── fb8eca0547d6_advanced_triggers_and_timescale.py # Triggers, Hypertables, Hash chaining
│   │       └── c72b10a90df1_align_spill_polygon_index.py  # Forward index alignment (idx_spills_polygon)
│   ├── app/                              # Application source code
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI entrypoint, lifespan startup, CORS, router mounting
│   │   ├── config.py                     # Pydantic Settings (DB, Redis, MinIO, Model paths)
│   │   ├── db/                           # SQLAlchemy database models & session factory
│   │   │   ├── __init__.py
│   │   │   ├── session.py                # AsyncSessionLocal, engine, get_session dependency
│   │   │   └── models/                   # SQLAlchemy ORM models (strictly matching DataBaseFinal.md)
│   │   │       ├── __init__.py
│   │   │       ├── enums.py              # Enum types (SpillStatusEnum, SceneStatusEnum, etc.)
│   │   │       ├── scene.py              # Table 3: scenes (wind_speed, wind_direction, footprint)
│   │   │       ├── spill.py              # Table 4: spills (14 columns, PostGIS MultiPolygon, review_notes)
│   │   │       ├── vessel.py             # Table 1: vessels
│   │   │       ├── track.py              # Table 2: tracks (AIS hypertable)
│   │   │       ├── cpa_event.py          # Table 5: cpa_events
│   │   │       ├── environmental_data.py # Table 6: environmental_data
│   │   │       ├── drift_run.py          # Table 7: drift_runs
│   │   │       ├── audit_log.py          # Table 8: audit_log (singular, SHA-256 hash chaining)
│   │   │       ├── ais_gap.py            # AIS gap tracking model
│   │   │       ├── attribution_score.py  # Vessel attribution scoring model
│   │   │       ├── dossier.py            # Evidence dossier model
│   │   │       └── job.py                # Background processing job tracking
│   │   ├── repositories/                 # Data Access Layer (Async Repository pattern)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                   # AsyncRepository[T] generic base class
│   │   │   ├── audit_repo.py             # AuditRepository (append-only, SHA-256 continuous hash chain)
│   │   │   ├── scene_repo.py             # SceneRepository (CRUD, wind retrieval)
│   │   │   └── spill_repo.py             # SpillRepository (ST_GeomFromText, selectinload scene context)
│   │   ├── schemas/                      # Pydantic v2 validation and serialization schemas
│   │   │   ├── __init__.py
│   │   │   ├── common.py                 # Spatial GeoJSON <-> WKT conversion helpers
│   │   │   ├── scene.py                  # SceneBase, SceneResponse (dynamic wind_u10 / wind_v10 @computed_field)
│   │   │   └── spill.py                  # SpillBase (14 columns), SpillCandidate, SpillFilterBatchRequest/Response
│   │   ├── services/                     # Business logic and domain service layer
│   │   │   ├── __init__.py
│   │   │   ├── filter_service.py         # FilterService (3-tier hybrid wind resolution, error isolation)
│   │   │   └── storage.py                # MinIO S3 object storage client
│   │   └── routers/                      # FastAPI API endpoint routers
│   │       ├── __init__.py
│   │       ├── health.py                 # GET /health (Async health checks: DB, Redis, MinIO)
│   │       └── spills.py                 # POST /api/v1/spills/filter, GET /api/v1/spills, GET /api/v1/spills/{id}
│   └── scripts/                          # Backend utility scripts
│       └── test_workflow.py              # End-to-end workflow verification script
├── core/                                 # Shared Core Intelligence Engines
│   ├── __init__.py
│   └── phase2_false_positive/            # Phase 2 ML Engine: False-Positive Lookalike Filter
│       ├── __init__.py
│       ├── dataset.py                    # PyTorch Dataset for SAR patches + ERA5 UV components
│       ├── model.py                      # ResNet-18 SAR-UV CNN model architecture + Temperature Scaling
│       ├── train.py                      # Training loop with focal loss, validation, temperature calibration
│       ├── evaluate.py                   # Evaluation metrics (ROC-AUC, Precision, Recall, ECE calibration)
│       ├── inference.py                  # SpillFilter production inference class (PyTorch + CSIRO ensemble)
│       ├── requirements.txt              # ML dependencies (torch, torchvision, scikit-learn, pillow)
│       └── checkpoints/                  # Trained model checkpoints
│           ├── best_model_sar_only.pth   # SAR single-channel CNN weights
│           ├── best_model_sar_speed.pth  # SAR + Wind Speed 2-channel CNN weights
│           ├── best_model_sar_uv.pth     # SAR + Wind U/V 3-channel CNN weights (T = 1.3788)
│           └── csiro_classifier.joblib   # 25-feature CSIRO Voting Ensemble (ROC-AUC: 1.0000)
├── data/                                 # Datasets and benchmark metadata
│   └── fp_filter/                        # False-positive filter datasets
│       ├── wind_metadata.json            # 5,630 CSIRO patches with matched ERA5 (u10, v10) vectors
│       └── csiro_patches/                # Benchmark SAR image patches
│           ├── oil/                      # Confirmed genuine mineral oil spill patches
│           └── non_oil/                  # Lookalikes (low-wind shadows, algal blooms, biogenic films)
├── docs/                                 # Architectural specifications, guides, and documentation
│   ├── PROJECT_CONTEXT.md                # Full context bundle for LLM ingestion
│   ├── phase2_benchmarks.md              # Model performance benchmarks across ablation variants
│   ├── walkthrough.md                    # Phase 2 ↔ DB integration walkthrough & verification logs
│   ├── pitch_deck/                       # Presentation assets and system diagrams
│   └── guides/                           # System architecture guides
│       ├── DataBaseFinal.md              # Ground-truth database contract (Tables 1-8, triggers, invariants)
│       ├── README.md                     # Architecture overview & setup instructions
│       ├── ARCHITECTURE.md               # Detailed system architecture diagram & component flow
│       ├── DEPLOYMENT.md                 # Production deployment & container orchestration guide
│       ├── BACKEND_SETUP.md              # Local backend setup and migration steps
│       ├── DOCKER_COMPOSE_QUICKSTART.md  # Docker quickstart guide
│       └── ...                           # Module-specific documentation
├── frontend/                             # User interface (React / Vite dashboard)
│   └── dashboard/                        # Web dashboard client
├── models/                               # Legacy model scripts (rebased to core/phase2_false_positive)
│   ├── common/schema.py                  # Candidate data structures
│   └── false_positive_filter/            # Legacy filter implementation
├── scripts/                              # Data processing & ablation study scripts
│   ├── join_era5_metadata.py             # Match Sentinel-1 patches with ERA5 NetCDF wind vectors
│   ├── run_ablation_study.py             # Run multi-mode ablation benchmark (sar_only vs sar_speed vs sar_uv)
│   └── show_tree.py                      # Print repository structure
├── tests/                                # Test suites
│   ├── test_phase2_db_integration.py     # Automated contract tests (GeoJSON/WKT, schemas, wind math, 3-tier filter)
│   ├── unit/                             # Unit tests
│   └── integration/                      # Integration tests
├── docker-compose.yml                    # Multi-container orchestration (db, redis, minio, backend)
├── .env.example                          # Environment variable template
└── README.md                             # Repository top-level README
```

---

## 3. Database Architecture & Ground Truth (`docs/guides/DataBaseFinal.md`)

### The Golden Rule
> **Do not use `Base.metadata.create_all()`.** All database tables, spatial indexes, triggers, and hypertables are strictly managed through Alembic migrations.

### Table Contract Summary

| Table | Name | Role & Invariants |
|---|---|---|
| **Table 1** | `vessels` | Ship registry (MMSI, IMO, callsign, vessel_type, dimensions). |
| **Table 2** | `tracks` | AIS trajectory points (TimescaleDB hypertable partitioned on `timestamp`). |
| **Table 3** | `scenes` | SAR imagery metadata (`wind_speed`, `wind_direction`, `footprint` polygon, `storage_uri`). |
| **Table 4** | `spills` | **The ONLY writable surface for Phase 2.** Exactly 14 columns. |
| **Table 5** | `cpa_events` | Closest Point of Approach calculations between vessels and spill polygons. |
| **Table 6** | `environmental_data` | Metocean data (ocean currents, waves, SST, ERA5 wind grid). |
| **Table 7** | `drift_runs` | Forward and backward hydrodynamic drift trajectories. |
| **Table 8** | `audit_log` | **Singular table name `audit_log`**. Append-only with cryptographic SHA-256 hash chaining. |

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

## 4. Phase 2 Machine Learning Engine (`core/phase2_false_positive/`)

### Architecture
- **Model**: PyTorch `ResNet-18` backbone adapted for multimodal inputs:
  - `sar_only`: 1-channel SAR amplitude.
  - `sar_speed`: 2-channel SAR + scalar normalized wind speed grid.
  - `sar_uv`: 3-channel SAR + directional $U_{10}$ and $V_{10}$ wind vector grids.
- **Calibration**: Post-hoc Temperature Scaling ($T = 1.3788$) ensures predicted probabilities represent true empirical risk (Expected Calibration Error $\le 0.05$).
- **Tabular Ensemble**: 25 physical backscatter, damping, texture, gradient, and contrast features evaluated by a `HistGradientBoosting` + `ExtraTrees` Voting Classifier trained on 5,630 CSIRO SAR patches (ROC-AUC: 1.0000).

### 3-Tier Hybrid Wind Resolution in `FilterService`
1. **Tier 1 (`scene_derived`)**: Derives $(u_{10}, v_{10})$ from `scenes.wind_speed` and `scenes.wind_direction`.
2. **Tier 2 (`metadata_json`)**: Looks up exact historical ERA5 vector for known benchmark patches from `data/fp_filter/wind_metadata.json`.
3. **Tier 3 (`none`)**: Fallback to neutral default `(None, None)`.

---

## 5. API Endpoints & Contracts

### `POST /api/v1/spills/filter`
- **Request Body**: `SpillFilterBatchRequest`
  ```json
  {
    "candidates": [
      {
        "scene_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "patch_path": "data/fp_filter/csiro_patches/oil/0_0_0_img_0bBRglmdLdC6cFxF_JAV_cls_1.jpg",
        "center_lat": 13.22,
        "center_lon": 80.32,
        "spill_polygon": { "type": "Polygon", "coordinates": [...] },
        "area_sq_km": 1.45,
        "detection_confidence": 0.88
      }
    ],
    "model_mode": "sar_uv",
    "threshold": 0.50
  }
  ```
- **Response**: `SpillFilterBatchResponse` (Strictly pinned fields: `confirmed`, `rejected`, `failed`, `model_mode`, `calibration_temperature`).
  - Confirmed oil spills inserted with `status = "confirmed"`.
  - Rejected lookalikes inserted with `status = "rejected"`, with explanation stored in `review_notes`.
  - Missing/corrupted images isolated in `failed: list[dict]` without aborting the batch transaction.

### `GET /api/v1/spills`
- Lists spill records with eager-loaded `scene` relationship (providing wind context via `SceneResponse`).

### `GET /health`
- Verifies asynchronous connectivity to PostgreSQL (`SELECT 1`), Redis (`PING`), and MinIO (`list_buckets`).

---

## 6. Verification Status & Test Results

1. **Contract & Unit Tests (`tests/test_phase2_db_integration.py`)**:
   - `test_geojson_wkt_conversion`: Passed (WKT MultiPolygon conversion).
   - `test_scene_derived_wind_components`: Passed ($U_{10}/V_{10}$ math).
   - `test_spill_table_contract_and_no_banned_columns`: Passed (Zero banned columns, exactly 14 allowed fields).
   - `test_pinned_batch_response_shape`: Passed (Response model validation).
   - `test_filter_service_hybrid_wind_resolution`: Passed (All 3 resolution tiers tested).
   - **Result**: `Ran 5 tests in 6.984s — OK`

2. **Inference Benchmarks**:
   - Genuine Oil Spill (`0_0_0_img_0bBRglmdLdC6cFxF_JAV_cls_1.jpg`): `is_oil = True`, `confidence = 0.9234` (92.34% confidence).
   - Lookalike Non-Oil (`0_0_0_img_01RNDdyOUhULo97s_SFr_cls_0.jpg`): `is_oil = False`, `confidence = 0.00072` (0.07% confidence, decisively rejected).
