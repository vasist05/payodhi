# ⚖️ Phase 6 — Forensic Evidence & Dossier Generation Guide

## 📌 Executive Summary

**Owner:** Person 5 (Forensic Attribution & Evidence Lead)  
**Depends On:** Phase 5 Attribution Output (`AttributionResult`), Phase 3 Drift (`DriftResult`), Phase 4 AIS (`VesselCandidate`)  
**Consumed By:** Phase 7 Frontend Dashboard & Regulatory Authorities (ICG / DG Shipping / Courts)

Phase 6 transforms algorithmic attribution scores into an **explainable, tamper-evident, court-admissible forensic dossier**. In high-stakes maritime enforcement, a raw number like "87/100" is insufficient for legal interdiction. Investigators and maritime tribunals require:
1. Clear explainability for each scored factor (XAI).
2. Explicit **"Why NOT this vessel"** disqualifications for alternative candidates.
3. Cryptographic **chain of custody** (SHA-256 hash sealing) ensuring forensic immutability.

---

## 🏛️ Architecture & Data Flow

```text
Phase 5: Attribution Ranking
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                 Phase 6: Evidence Builder                   │
│                                                             │
│  1. Factor Explainers (✅ Positive / ❌ Negative Bullets)   │
│  2. "Why NOT This Vessel" Differential Analysis             │
│  3. Investigative Narrative Synthesis                       │
│  4. SHA-256 Dossier Integrity Sealing                       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Court-Admissible Forensic Dossier (JSON / Exportable PDF)
```

---

## 🔍 Core Deliverables

### 1. Per-Factor Evidence Bullet Generation

For every candidate vessel evaluated, generate plain-English forensic findings across all attribution pillars:

```text
Vessel: DAWN KANCHIPURAM (MMSI: 419000123)
🛰️ Spill Detection: 2024-01-15 14:30 UTC
🌊 Estimated Release Window: 2024-01-15 10:00 – 12:30 UTC
✅ Proximity: Vessel closest point of approach (CPA) was 1.2 km from estimated spill origin.
✅ Drift Agreement: 89% agreement with OpenDrift reverse hydrodynamic trajectory.
✅ Temporal Alignment: Vessel transit coincided precisely with estimated release window (TCPA offset: 12 min).
✅ Vessel Profile: Oil/Chemical Tanker carrying Heavy Fuel Oil (high risk category).
⚠️ AIS Discipline: 42-minute AIS transmission gap observed during transit across spill corridor.
Attribution Score: 89.6/100 — Classification: Strong Evidence
```

### 2. "Why NOT This Vessel" Differential Disqualification

Every non-primary candidate must feature transparent disqualifying factors to defend against claims of arbitrary selection:

```text
Vessel: SEASPAN FRASER (MMSI: 419000456) — Score: 34.2/100
❌ Proximity: Nearest approach was 14.6 km from estimated spill origin (outside 5 km corridor).
❌ Trajectory Inconsistency: Vessel heading 210° conflicts with northwest spill drift vector.
❌ Temporal Mismatch: Arrived in sector 3.5 hours after estimated release window closed.
✅ Vessel Category: Container ship (bunker fuel capacity confirmed).
```

### 3. Investigative Narrative Synthesis

Generate a legally neutral, objective synthesis statement:
> *"Forensic analysis identifies DAWN KANCHIPURAM (MMSI: 419000123) as the most probable source of the Ennore oil spill (Attribution Score: 89.6/100, High Confidence). Primary evidence includes a CPA of 1.2 km to the back-projected origin, 89% hydrodynamic drift concordance, and an unexplained 42-minute AIS blackout during release. Two alternative vessels were eliminated due to spatial and temporal non-concordance."*

### 4. Forensic Dossier & Chain of Custody Model

The output dossier must comply with Table 11 (`forensic_dossiers`) and Table 12 (`dossier_chain_of_custody`) in [`DataBaseFinal.md`](./DataBaseFinal.md):
- **Incident Metadata**: Satellite sensor ID, detection timestamp, bounding polygon.
- **Hydrodynamic Context**: Wind, current leeway, backward drift particle envelope.
- **Full Candidate Table**: All analyzed vessels with scores, confidence, and ranks.
- **SHA-256 Hash**: Cryptographic digest of raw telemetry, drift runs, and ranking outputs.

---

## 🚩 AI Red Flags (Traps to Avoid)

| ❌ Dangerous Anti-Pattern | ✅ Correct Implementation |
| :--- | :--- |
| **Accusatory Language**: Generating text like *"DAWN KANCHIPURAM dumped oil illegally"*. | **Forensic Neutrality**: Use *"Telemetry indicates spatial and temporal concordance with the release zone."* |
| **Silent Exclusions**: Omitting lower-ranked vessels from the report. | **Full Candidate Ledger**: Detail all vessels within the spatial-temporal search window with explicit disqualifiers. |
| **Static Strings**: Hardcoding factor summaries. | **Dynamic Thresholding**: Map scores and metrics dynamically to descriptive evidence bullets. |
| **Unsealed Output**: Exporting JSON without cryptographic hashing. | **SHA-256 Digest**: Compute a SHA-256 hash over all input metrics to guarantee evidentiary integrity. |

---

## 📋 Edge Cases & Safeguards

| Scenario | Expected Engine Behavior |
| :--- | :--- |
| **Zero AIS candidates in zone** | Flag potential "Dark Vessel" scenario; output spill origin coordinates and recommend radar/optical cross-check. |
| **Top two vessels within 5% score margin** | Downgrade outcome to `AMBIGUOUS_EVIDENCE`; generate side-by-side comparison matrix. |
| **AIS Gap across all candidates** | Explicitly document potential coastal receiver blackout or jamming in the narrative. |
| **Missing Environmental Data** | Flag degraded drift confidence in the dossier summary bullets. |
