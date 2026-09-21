# 🌊 Payodhi — Maritime Oil Spill Detection & Forensic Attribution Engine

Payodhi is an end-to-end maritime intelligence and forensic attribution system designed to detect oceanic oil spills from satellite imagery (SAR/Optical), reconstruct vessel trajectories from historical AIS tracks, model reverse hydrodynamic drift (hindcast/forecast), and generate court-admissible forensic dossiers pinpointing responsible polluters.

---

## 📁 Repository Structure

```text
payodhi/
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
│
├── docs/
│   └── guides/
│       ├── README.md              # Build guides index & roadmap
│       ├── DataBaseFinal.md       # Complete database & architecture specification
│       ├── phase5Final.md         # 7-Pillar Defence-Grade Attribution Engine guide
│       └── phase6Final.md         # Forensic Evidence & Dossier Generation guide
│
├── backend/
│   ├── alembic/
│   │   └── versions/              # Database migration versions
│   ├── app/
│   │   ├── db/
│   │   │   └── models/            # SQLAlchemy / GeoAlchemy2 models
│   │   ├── schemas/               # Pydantic v2 validation models
│   │   ├── routers/               # FastAPI route endpoints
│   │   ├── services/              # Business logic & pipeline orchestrators
│   │   └── repositories/          # Database query abstractions
│   ├── requirements.txt           # Python backend dependencies
│   └── Dockerfile                 # Backend container definition
│
├── core/
│   ├── phase1_sar/                # Phase 1: SAR detection & U-Net segmentation
│   ├── phase2_false_positive/     # Phase 2: False positive suppression & CSIRO filter
│   ├── phase3_drift/              # Phase 3: Reverse hydrodynamic drift (OpenDrift)
│   ├── phase4_ais/                # Phase 4: AIS trajectory reconstruction & dark vessels
│   ├── phase5_attribution/        # Phase 5: 7-Pillar Evidential Fusion ranking engine
│   ├── phase6_dossier/            # Phase 6: Explainable evidence & forensic dossier export
│   └── common/                    # Shared geospatial math, constants & schemas
│
├── models/
│   ├── sar_segmentation/          # Model weights for SAR segmentation
│   └── false_positive/            # Model weights for CSIRO & lookalike filter
│
├── data/
│   ├── csiro/                     # CSIRO benchmarking dataset & wind metadata
│   ├── fixtures/                  # Mock payloads & test inputs
│   └── incidents/                 # Historical ground-truth case data (Ennore, Mumbai, Haldia)
│
├── frontend/
│   └── dashboard/
│       └── src/
│           ├── components/        # React UI components (Map, CandidateTable, DossierView)
│           ├── pages/             # Route views & investigation dashboard
│           └── services/          # API client & WebSocket connections
│
├── scripts/                       # Training, benchmarking, and database seeding utilities
│
└── tests/
    ├── unit/                      # Fast unit tests for core modules
    └── integration/               # End-to-end pipeline & database integration tests
```

---

## 🛠️ Infrastructure Services

| Service | Technology | Port | Purpose |
|---|---|---|---|
| **Database** | TimescaleDB (PostgreSQL 16 + PostGIS) | `5432` | Time-series AIS storage, geospatial queries, and incident ledgers |
| **Cache & Queue** | Redis 7 | `6379` | Task queuing, pipeline worker communication, and fast caching |
| **Object Store** | MinIO | `9000` / `9001` | GeoTIFF rasters, satellite imagery, and forensic dossier PDFs |

---

## 📖 Architecture & Phase Guides

Detailed architectural blueprints and phase implementation guides are located in [`docs/guides/`](docs/guides/):

- **[System Database & Architecture Guide](docs/guides/DataBaseFinal.md)**: 12-table TimescaleDB + PostGIS schema, spatial indexes, immutability constraints, and core SQL queries.
- **[Phase 5 Attribution Ranking Engine Guide](docs/guides/phase5Final.md)**: 7-pillar evidential fusion, Monte Carlo null permutation tests ($p < 0.001$), and legal dossier scoring.
- **[Phase 6 Forensic Evidence & Dossier Guide](docs/guides/phase6Final.md)**: XAI evidence bullets, "Why NOT this vessel" disqualification logic, and SHA-256 chain-of-custody sealing.
