# 🌊 Payodhi — Maritime Oil Spill Detection & Forensic Attribution Engine

Payodhi is an end-to-end maritime intelligence and forensic attribution system designed to detect oceanic oil spills from satellite imagery (SAR/Optical), reconstruct vessel trajectories from historical AIS tracks, model reverse hydrodynamic drift (hindcast/forecast), and generate court-admissible forensic dossiers pinpointing responsible polluters.

---

## 📁 Repository Structure

```text
payodhi/
├── docs/
│   └── guides/
│       ├── README.md              # Build guides overview & progress
│       ├── DataBaseFinal.md       # Complete database & architecture specification
│       └── phase5Final.md         # 7-Pillar Defence-Grade Attribution Engine guide
├── backend/
│   ├── alembic/                   # Database migrations (TimescaleDB / PostGIS)
│   └── app/                       # FastAPI application & core pipeline modules
├── frontend/                      # Forensic dashboard interface
├── models/
│   ├── sar_segmentation/          # SAR segmentation model checkpoints
│   └── false_positive/            # CSIRO wind & lookalike filters
├── data/
│   └── csiro/                     # Benchmarking datasets & metadata
├── .gitignore
└── README.md
```

---

## 📖 Architecture & Build Guides

Detailed architectural blueprints and phase implementation guides are located in [`docs/guides/`](docs/guides/):

- **[System Database & Architecture Guide](docs/guides/DataBaseFinal.md)**: 12-table TimescaleDB + PostGIS schema, spatial indexes, immutability constraints, and core SQL queries.
- **[Phase 5 Attribution Ranking Engine Guide](docs/guides/phase5Final.md)**: 7-pillar evidential fusion, Monte Carlo null permutation tests ($p < 0.001$), and legal dossier generation.
- **[Guides Overview](docs/guides/README.md)**: Roadmap and phase breakdown.
