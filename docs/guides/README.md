# 📚 Payodhi — Architecture & Phase Build Guides

This directory contains detailed implementation guides and architecture specifications for the Payodhi oil spill detection and forensic attribution pipeline.

---

## 📖 Available Guides

| Document | File | Scope | Status |
| :--- | :--- | :--- | :--- |
| **System Database & Architecture Guide** | [`DataBaseFinal.md`](./DataBaseFinal.md) | TimescaleDB + PostGIS (12 tables), data model, schema migrations, and spatial queries | ✅ Ready |
| **Phase 5 — Attribution Ranking Engine** | [`phase5Final.md`](./phase5Final.md) | 7-pillar evidential fusion, Monte Carlo null permutations, and legal dossier scoring | ✅ Ready |
| **Phase 6 — Forensic Evidence & Dossier Generation** | [`phase6Final.md`](./phase6Final.md) | XAI evidence bullets, why-not differential analysis, narrative synthesis, SHA-256 chain of custody | ✅ Ready |
| Phase 1 — SAR/Optical Detection & Segmentation | `phase1_detection.md` | Dual-polarization U-Net, SAR preprocessing | 🔜 Planned |
| Phase 2 — False-Positive Suppression | `phase2_fp_filter.md` | CSIRO wind & lookalike classifiers | 🔜 Planned |
| Phase 3 — Drift Modeling | `phase3_drift_model.md` | OpenDrift backward hindcast & forward forecast | 🔜 Planned |
| Phase 4 — AIS Reconstruction & Correlation | `phase4_ais_pipeline.md` | Trajectory reconstruction, dark vessel detection | 🔜 Planned |

---

## 🛠️ How to Use These Guides

1. **Read the relevant guide** before implementing modules or migrations.
2. **Review schema constraints & immutability rules** in [`DataBaseFinal.md`](./DataBaseFinal.md) before writing database logic.
3. **Follow the 7-pillar scoring specification** in [`phase5Final.md`](./phase5Final.md) for attribution ranking.
4. **Adhere to forensic neutrality & chain-of-custody standards** in [`phase6Final.md`](./phase6Final.md) for evidence output.
