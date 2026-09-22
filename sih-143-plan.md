# SIH26143 — Master Build Plan
## Oil Spill Detection & Vessel Attribution System — Indian Waters

---

## 0. OFFICIAL PROBLEM STATEMENT (keep this at the top always)

**Organization:** National Technical Research Organisation (NTRO)
**Theme:** Space Technology | **Category:** Software

> "Leveraging satellite imagery to determine oil spills at sea along with AIS data correlations to identify the vessel responsible for the spill."

**Our scoping decision:** Built and validated for Indian coastal waters (Gulf of Kutch/Kandla/Mumbai High, Chennai/Ennore, Haldia/Sundarbans), because (a) region-specific training measurably outperforms generic global models per published research, (b) NTRO's real operational interest is Indian maritime security, and (c) our validation cases (Haldia 2018, Chennai 2017) are Indian incidents.

**Aim:** Detect oil spills from satellite SAR imagery, then correlate with AIS ship-tracking data to identify the vessel most likely responsible — outputting an evidence-backed ranked list, not just a detection.

---

## 1. TEAM STRUCTURE — 6 MEMBERS

| # | Role | Owns | Primary Phases |
|---|------|------|-----------------|
| 1 | Detection Lead | SAR spill segmentation model | Phase 1 |
| 2 | CV/Robustness Lead | False-positive filtering, SAR-UV wind integration | Phase 2 |
| 3 | Drift/Physics Lead | Backward + bidirectional drift simulation | Phase 3 |
| 4 | Data Engineering Lead | AIS pipeline, dark-vessel detection, behavioral anomaly | Phase 4 |
| 5 | Backend/Logic Lead | Attribution ranking engine, evidence chain | Phase 5, 6 |
| 6 | Frontend/Integration Lead | Dashboard, report generator, end-to-end pipeline wiring | Phase 7 |

**Shared responsibilities (all 6 members):**
- Phase 0 (setup) — everyone participates once
- Phase 8 (validation) — whole team runs the integrated pipeline together against real cases
- Phase 9 (pitch) — whole team contributes; Frontend/Integration Lead typically assembles the final demo flow

**Why this split works for a 6-person team specifically:** Each phase from 1–6 has a clear, independent owner so two people are never blocked waiting on the same file. Phases 1+2 (Detection Lead + CV/Robustness Lead) work closely together since Phase 2 directly extends Phase 1's output. Phases 5+6 are combined under one person because the evidence chain (Phase 6) is really just an explainability wrapper around the ranking logic (Phase 5) — splitting them across two people would cause constant back-and-forth on the same data structures.

---

## 2. GIT WORKFLOW FOR A 6-PERSON TEAM

### 2.1 Branch structure
```
main         → always stable, only working, demo-ready code
dev          → integration branch, everyone merges here first
feature/*    → one branch per person per task, e.g.:
   feature/sar-detection          (Person 1)
   feature/false-positive-filter  (Person 2)
   feature/drift-simulation       (Person 3)
   feature/ais-pipeline           (Person 4)
   feature/attribution-engine     (Person 5)
   feature/dashboard              (Person 6)
```

### 2.2 Daily workflow (every person, every session)
```bash
git checkout dev
git pull                          # always start with latest
git checkout -b feature/your-task # if starting new work, or:
git checkout feature/your-task    # if continuing existing work
git pull origin dev --rebase      # keep your branch updated with dev's latest changes
... do your work ...
git add .
git commit -m "clear, specific message: what changed and why"
git push -u origin feature/your-task
```

### 2.3 Pull Request (PR) rules for this team size
- Every PR into `dev` needs **at least 1 reviewer** — pair people who work on adjacent modules (e.g., Person 1 reviews Person 2's PRs and vice versa, since their code interacts directly)
- **Never push directly to `main`.** Only merge `dev` → `main` at agreed milestones (end of each phase, or before a demo run)
- Keep PRs small and specific to one phase/feature — a PR titled "Phase 1: SAR detection base model" is reviewable; a PR titled "various updates" is not

### 2.4 Avoiding merge conflicts with 6 people
- Because each person owns a distinct folder (`models/detection/`, `models/false_positive_filter/`, `models/drift_model/`, `backend/ais_pipeline/`, `backend/attribution_engine/` + `backend/evidence_engine/`, `frontend/dashboard/`), most work naturally doesn't overlap at the file level — this folder-per-owner structure is deliberately designed to minimize conflicts
- The main conflict risk is in shared integration files (e.g., `backend/api/main.py`, which calls everyone's modules). Assign **Person 6 (Frontend/Integration Lead)** as the sole owner of wiring modules together into `main.py` — others expose clean functions/APIs from their module, Person 6 integrates them, so only one person is regularly editing the shared integration point

### 2.5 Project board setup
GitHub → Projects → New board with columns: `Backlog`, `In Progress`, `In Review`, `Done`. Add every checklist item from this document as a card, assigned to the relevant person. Update it daily — this is your team's single source of truth for who's doing what.

### 2.6 Sync cadence
- **Daily 15-minute standup** (in person or on call): what you did, what you're doing next, any blockers
- **End-of-phase sync:** whoever owns that phase demos their working module to the whole team before merging to `main` — this catches integration issues early rather than at the final demo

---

## 3. PHASE-BY-PHASE DEEP BUILD PLAN

---

### PHASE 0 — Project & GitHub Setup
**Owner:** Whole team | **Goal:** Establish shared infrastructure so 6 people can work in parallel without collision.

**Deep steps:**
1. Create GitHub org/repo (Team Lead or Person 6)
2. Add all 6 members as collaborators
3. Install Git locally for everyone; verify with `git --version`
4. Clone repo to each laptop
5. Create `dev` branch, push it
6. Create full folder structure (as detailed in section 4 below — one folder per owner)
7. Add `.gitkeep` to every empty folder
8. Write `.gitignore`:
   ```
   *.h5
   *.pt
   *.ckpt
   checkpoints/
   data/raw/
   data/processed/
   venv/
   __pycache__/
   .env
   .DS_Store
   .vscode/
   ```
9. Create `docs/problem_statement.md` (paste Section 0 above), `docs/research_notes.md`, `docs/build_checklist.md` (this whole document)
10. Set up GitHub Projects board with all phases as cards, assigned per owner
11. Push everything to `main` as the initial commit

---

### PHASE 1 — Detection Foundation
**Owner:** Person 1 (Detection Lead) | **Supports:** Person 2

**What we're solving:** Take a raw SAR satellite image and produce a pixel-level mask marking where an oil spill likely is. This is a supervised deep learning segmentation task (CNN, U-Net architecture) — genuinely ML, not a rule-based script.

**Research papers integrated into this phase:**
- Suez Canal DeepLabv3+ study (region-specific fine-tuning outperforms generic global training) — justifies our two-stage global→India training strategy
- MobileUNet architecture paper — justifies U-Net family as the proven baseline for SAR spill segmentation
- Zenodo Sentinel-1 SAR Oil Spill dataset (DOIs 10.5281/zenodo.8346860, 10.5281/zenodo.8253899) — our primary open global dataset
- Deep-SAR Oil Spill (SOS) dataset — our secondary open global dataset, multi-satellite (Sentinel-1 + ALOS PALSAR)

**Deep steps:**

1. **Environment setup** — inside `models/detection/`:
   ```bash
   python -m venv venv
   source venv/bin/activate   # or venv\Scripts\activate on Windows
   pip install torch torchvision numpy pillow rasterio matplotlib opencv-python segmentation-models-pytorch
   ```

2. **Download both open datasets:**
   - Zenodo: 1,200 images, 2048×2048, Sigma0/dB, TIFF, with masks
   - Kaggle SOS: 8,070 images, already 256×256, Sentinel-1 + ALOS PALSAR

3. **Resolve the format mismatch (critical — skipping this crashes training):**
   - Zenodo images are 2048×2048; SOS images are 256×256 — must be unified
   - Zenodo is raw dB/Sigma0 GeoTIFF; SOS is already preprocessed/scaled — must be normalized to match
   - **Tiling script:** write a Python script (`scripts/tile_dataset.py`) using `rasterio`/`opencv-python` to slide a non-overlapping 256×256 window across each Zenodo image and its mask, producing ~64 tiles per image (8×8 grid on a 2048×2048 image). Filter out blank/empty tiles.
   - **Normalization:** rescale all pixel values (from both sources, post-tiling) to a consistent 0.0–1.0 range

4. **Organize combined dataset:**
   ```
   data/labeled/
   ├── images/   → tiled Zenodo patches + SOS images, combined
   └── masks/    → matching masks
   ```
   Create reproducible 80/20 train/validation split, save as `train_list.txt` / `val_list.txt`

5. **Build the model** (`models/detection/model.py`):
   ```python
   import segmentation_models_pytorch as smp
   model = smp.Unet(
       encoder_name="resnet34",
       encoder_weights="imagenet",   # free head-start from ImageNet pretraining
       in_channels=1,
       classes=1,
   )
   ```

6. **Write the Dataset/DataLoader class** to feed image/mask pairs in batches

7. **Choose loss + optimizer:** Dice Loss (or Dice+BCE combined) — standard for segmentation where most pixels are background; Adam optimizer, learning rate ~1e-4

8. **Train the base ("global pretrained") model:**
   - Train 20–50 epochs on the combined Zenodo+SOS dataset
   - Monitor validation IoU/F1 each epoch to catch overfitting
   - Save: `models/detection/checkpoints/base_model.pth` (gitignored — document regeneration steps in `data/README.md` instead)

9. **India-specific fine-tuning:**
   - Define AOIs: Gulf of Kutch/Kandla/Mumbai High, Chennai/Ennore, Haldia/Sundarbans
   - Download Sentinel-1 scenes for these zones via Copernicus, including dates around the Chennai 2017 and Haldia 2018 incidents
   - Run the base model on these Indian images to get rough auto-predictions
   - Manually correct predictions (fix missed spills, remove false marks) — target 300+ labeled Indian images
   - Load `base_model.pth`, continue training only on this Indian set for ~10–15 epochs at a lower learning rate

10. **Evaluate:** compute IoU and F1-score on held-out Indian validation images; compare honestly against published benchmark numbers for your pitch slide

**Git handling:** Branch `feature/sar-detection`, commits separated by milestone ("add tiling script", "add base global model", "add India fine-tuned model"), PR into `dev` reviewed by Person 2.

---

### PHASE 2 — False-Positive Filtering
**Owner:** Person 2 (CV/Robustness Lead) | **Depends on:** Phase 1 output

**What we're solving:** SAR "dark patches" aren't always oil — calm water, algae/biogenic slicks, wind shadows, and ship wakes all look similar. This phase builds a secondary filter to distinguish real oil from lookalikes, which is the single most-cited weak point in existing spill-detection systems.

**Research paper integrated:**
- 2026 IEEE J-STARS "Wind-Field-Integrated Deep Learning for Marine Oil Spill Detection" — uses ERA5 U10/V10 wind vector components (not just wind speed) as auxiliary model inputs. Reported results: 89.4% precision, 83.4% recall, 85.7% F1, 2.6% false-positive rate; median false-positive rate in low-wind regions dropped from 86.8% to 0.9% versus a wind-blind (VV-only) model. This is your strongest quotable statistic.

**Deep steps:**

1. **Collect lookalike examples:** use the CSIRO Kaggle dataset's labeled look-alike/no-oil examples, plus any hard negatives from your Indian AOI downloads (calm patches, coastal algal bloom zones)

2. **Source wind data:** download ERA5 reanalysis wind data (U10 = eastward component, V10 = northward component) for the same time/location as each SAR scene — available from Copernicus Climate Data Store

3. **Build the SAR-UV input configuration:** instead of feeding the model raw wind speed as a single number, feed U10 and V10 as two separate additional input channels alongside the SAR image itself — this gives the model directional wind context, which is what the referenced paper found most effective at killing false positives

4. **Build the secondary classifier** (`models/false_positive_filter/model.py`): a CNN classifier (can reuse a ResNet-style backbone) that takes [SAR patch + U10 channel + V10 channel] and outputs "true oil" vs. "lookalike"

5. **Train it** on your combined true-spill vs. lookalike examples, using the same train/val discipline as Phase 1

6. **Chain it after Phase 1:** Phase 1's U-Net proposes candidate spill regions → Phase 2's classifier filters out the ones that are actually lookalikes → only surviving regions proceed to Phase 3

7. **Build the "False-Positive Lab" demo set:** curate side-by-side examples (true oil slick / calm water / algae bloom / ship wake / wind shadow) with your model's prediction and confidence for each — this becomes a dedicated, high-impact pitch slide

**Git handling:** Branch `feature/false-positive-filter`, builds on Person 1's merged Phase 1 code, PR reviewed by Person 1.

---

### PHASE 3 — Drift Reconstruction
**Owner:** Person 3 (Drift/Physics Lead) | **Depends on:** Phase 1+2 output (confirmed spill polygon + detection timestamp)

**What we're solving:** By the time a spill is detected, the responsible vessel has moved on. We need to work backward from the spill's location and detection time to estimate where and when it actually originated — because that's the point in time/space where the responsible vessel needs to have been.

**Research/methodology integrated:**
- NOAA's GNOME model and the open-source OpenDrift framework — established, physics-based ocean trajectory simulation tools (wind drag + ocean currents + Coriolis effect) used operationally for oil-spill and drift forecasting. We build our simulation logic following this established physics approach rather than inventing new drift equations.
- Bidirectional drift concept (from your research documents) — rather than only simulating backward from the spill, also simulate forward from each candidate vessel's known track, then compare the two for agreement — a stronger, more defensible correlation than simple point-distance measurement.

**Deep steps:**

1. **Source environmental data:** ERA5 wind data (reuse Phase 2's U10/V10 pull) and ocean current reanalysis data (e.g., HYCOM or Copernicus Marine Service current fields) for your Indian AOIs

2. **Implement backward drift simulation** (`models/drift_model/drift_sim.py`): given a spill polygon's centroid, detection time, and local wind/current vectors, apply a drift equation (velocity = wind drag coefficient × wind vector + ocean current vector + Coriolis correction) stepped backward in time in small increments (e.g., every 15–30 minutes) until you reach a plausible release time window (e.g., several hours before detection)

3. **Convert single-point origin into a probability region (heatmap), not a single coordinate:** since drift modeling has real uncertainty, run the simulation with small perturbations to your input assumptions (slightly different wind/current estimates) multiple times (a basic Monte Carlo-style approach) and aggregate the resulting origin points into a heatmap — high-density areas = high likelihood, sparse areas = low likelihood. This is scientifically honest and directly differentiates you from teams claiming a single exact coordinate.

4. **Implement forward simulation from candidate vessels (bidirectional check):** once Phase 4 gives you a list of candidate vessels with known historical positions, run the same drift physics forward from each vessel's position at various times, and compare the resulting predicted spill locations against the actual detected spill location/time. Strong agreement between backward-from-spill and forward-from-vessel = strong evidence.

5. **Output format:** origin probability heatmap (for the dashboard) + a structured "release window" (time range + spatial region) that Phase 4/5 will consume

**Git handling:** Branch `feature/drift-simulation`. This module is relatively independent — mainly needs Phase 1+2's output format agreed upon early (coordinate + timestamp schema) so integration is smooth. PR reviewed by Person 4 (since their AIS module directly consumes this output).

---

### PHASE 4 — AIS Correlation & Dark-Vessel Detection
**Owner:** Person 4 (Data Engineering Lead) | **Depends on:** Phase 3 output (origin region + time window)

**What we're solving:** Given the estimated origin region/time, find which real ships were actually there — including ships that were physically present but didn't broadcast AIS (deliberately or otherwise), which is a real, documented evasion tactic.

**Research paper integrated:**
- University of New Hampshire Center for Coastal and Ocean Mapping study on AIS data for enhanced coastal security, including an oil-spill tracking application — confirms AIS-based spill attribution has real prior research grounding; your dark-vessel addition is the gap you close beyond this prior work.

**Deep steps:**

1. **Source AIS data:** pull historical AIS position records for your Indian AOIs and relevant time windows from a free-tier provider (e.g., AISHub)

2. **Build the correlation engine** (`backend/ais_pipeline/correlate.py`): for the origin region/time window from Phase 3, query which vessels had AIS positions within that spatial/temporal window; output a candidate list with each vessel's position, timestamp, speed, heading, and static data (type, size, destination)

3. **Build the dark-vessel module** (`backend/ais_pipeline/dark_vessel.py`): this requires a second detection source — count/positions of vessels *visible in the SAR imagery itself* (a simpler CV task: bright point/blob detection for ship-sized radar returns, distinct from the oil-spill segmentation model). Compare SAR-detected vessel count/positions against AIS-reporting vessels in the same scene. A vessel present in SAR but absent from AIS = flagged as an "AIS-invisible candidate requiring further investigation" — deliberately not stated as "the polluter," since this needs careful, defensible framing

4. **Build behavioral anomaly scoring** (`backend/ais_pipeline/fetch_ais.py` + supporting logic): from each candidate vessel's AIS track, calculate simple anomaly indicators — sudden speed changes, unexpected route deviation, AIS signal gaps, sharp course changes. Score each vessel 0–100 on "behavioral anomaly," explicitly framed as raising investigative priority, not as proof of guilt

5. **Output format:** structured list of candidate vessels, each with position/time match data, dark-vessel flag (yes/no), and behavioral anomaly score — passed to Phase 5

**Git handling:** Branch `feature/ais-pipeline`. PR reviewed by Person 3 (drift data consumer/producer relationship) and Person 5 (main consumer of this output).

---

### PHASE 5 — Attribution Ranking Engine
**Owner:** Person 5 (Backend/Logic Lead) | **Depends on:** Phase 3 (drift/bidirectional agreement) + Phase 4 (candidate vessels) output

**What we're solving:** Take everything computed so far and produce a ranked, weighted, defensible list of "most probable source" vessels — not a black-box single number.

**Research/methodology integrated:**
- General maritime risk-profiling literature on AIS-based vessel-type/cargo pollution-risk prioritization — justifies weighting tanker/chemical-carrier vessel types more heavily as a legitimate, literature-backed factor, not an assumption

**Deep steps:**

1. **Design the multi-factor weighted scoring formula** (`backend/attribution_engine/ranking.py`):
   ```
   Attribution Score = 
       0.35 × drift_agreement_score    (from Phase 3 bidirectional comparison)
     + 0.25 × time_overlap_score       (from Phase 3/4 timing match)
     + 0.20 × spatial_proximity_score  (from Phase 4 position match)
     + 0.10 × vessel_characteristics_score (type/cargo priors)
     + 0.10 × behavioral_anomaly_score (from Phase 4)
   ```
   These weights are a starting point — validate and adjust them against your Phase 8 real historical cases rather than treating them as fixed

2. **Add the voyage/cargo-history sub-step:** cross-reference each candidate vessel's AIS track against known port-call history and, where available, recent cargo-transfer records — was this vessel recently confirmed carrying oil/chemicals? Use this to adjust that specific vessel's "vessel characteristics" sub-score up or down, rather than applying a flat assumption based on vessel type alone

3. **Rename and reframe the output:** call it "**Attribution Score: X/100**" — never "AI confidence" or "probability of guilt." Attach a standing disclaimer: *"Higher score indicates stronger evidentiary alignment; this is not a legal determination of responsibility."* This single wording choice is a real defensibility improvement for an NTRO audience.

4. **Build the three-outcome logic:**
   - 🟢 **Strong attribution** — one candidate scores clearly above others with strong multi-factor agreement
   - 🟡 **Inconclusive** — multiple candidates score similarly, no clear standout
   - 🔴 **Insufficient evidence** — no candidate meets a minimum threshold score
   Don't force a "culprit" output every time — a system that knows when it doesn't know is more credible, not less.

**Git handling:** Branch `feature/attribution-engine`. PR reviewed by Person 4 (data producer) and Person 6 (consumer for dashboard).

---

### PHASE 6 — Evidence & Explainability Layer
**Owner:** Person 5 (same as Phase 5 — natural extension) | **Depends on:** Phase 5 output

**What we're solving:** A bare score isn't enough for an investigator — they need to see *why* a vessel ranked where it did, and why others were ranked lower.

**Research concept integrated:**
- General Explainable AI (XAI) literature on transparent decision-support systems for high-stakes domains — justifies building a transparent evidence chain rather than a black-box output, positioning this as an applied XAI design choice you can name explicitly in your pitch

**Deep steps:**

1. **Build the evidence chain generator** (`backend/evidence_engine/evidence_builder.py`): for each candidate vessel, assemble a structured breakdown:
   ```
   Vessel A
   🛰️ Spill detected: 14:32 UTC
   🌊 Estimated origin window: 14:05–14:20 UTC
   📍 Vessel was 2.8 km from estimated origin
   🧭 Vessel moving in a compatible direction
   💨 Bidirectional drift agreement: high
   🚢 Vessel type: Oil/chemical tanker (recent cargo history: crude oil, per port records)
   📡 AIS available throughout critical period
   Attribution Score: 87/100 — Evidence strength: Strong
   ```

2. **Build the "why NOT this vessel" feature:** for every lower-ranked candidate, generate the specific disqualifying/weakening factors:
   ```
   Vessel B — Attribution Score: 41/100
   ❌ 14 km from estimated origin (too far)
   ❌ Drift direction inconsistent with vessel heading
   ❌ Arrived in area after estimated release window
   ✅ Correct vessel category (tanker)
   ```

3. **Wire this into a final narrative statement:** "Most probable source: Vessel A — Attribution Score 87/100 — Evidence strength: Strong — Key evidence: temporal + spatial + bidirectional drift agreement — Alternative candidates: 2 (Vessel B: 41/100, Vessel C: 28/100)"

**Git handling:** Same branch/PR flow as Phase 5, since it's a direct extension — can be a follow-up commit on `feature/attribution-engine` or a new `feature/evidence-engine` branch reviewed by Person 6.

---

### PHASE 7 — Investigator Dashboard
**Owner:** Person 6 (Frontend/Integration Lead) | **Depends on:** All previous phases' outputs

**What we're solving:** Present the entire pipeline's output — detection, drift, attribution, evidence — as a usable, demoable investigative tool, not just raw JSON.

**Deep steps:**

1. **Set up frontend project** (`frontend/dashboard/`): initialize with your chosen framework (e.g., `npm create vite@latest` for a React app)

2. **Build the map view:** display the spill polygon (from Phase 1/2), the origin probability heatmap (from Phase 3), and candidate vessel positions (from Phase 4) on an interactive map (e.g., Leaflet or Mapbox)

3. **Build the ranked candidate list panel:** display each vessel's Attribution Score, evidence summary, and expandable "why NOT" details for lower-ranked ones

4. **Wire up the backend API** (`backend/api/main.py`, owned/integrated by Person 6): expose endpoints that each module's owner has built clean functions for — e.g., `/detect`, `/drift`, `/correlate`, `/rank` — and chain them into one end-to-end pipeline call for the demo

5. **Stretch — Time Machine slider:** a draggable timeline control that, as the user scrubs backward, animates the spill location (per drift simulation), vessel positions (per AIS history), and the shrinking/moving probable release zone. This is your single highest-impact demo visual if time allows.

6. **Stretch — Investigation Report Generator** (`backend/report_generator/generate_report.py`): auto-generate a PDF summarizing incident details, environmental conditions, ranked candidates table, evidence map, and stated model limitations — turns the project from "a dashboard" into "a decision-support deliverable"

**Git handling:** Branch `feature/dashboard`. Since this branch integrates everyone else's modules, Person 6 should pull `dev` frequently (daily) to stay current as other modules merge in. PR reviewed by whichever team member owns the module being freshly integrated that week.

---

### PHASE 8 — Validation
**Owner:** Whole team, coordinated by Person 5 (since attribution output is what's being validated)

**What we're solving:** Prove the pipeline actually works using real, documented historical incidents — this is your strongest pitch asset and the thing that separates you from teams demoing on synthetic data.

**Deep steps:**

1. **Case 1 — Haldia Port oil spill (July 2018):** research and gather the documented spill location, approximate time, and involved vessel(s); pull matching Sentinel-1 SAR imagery and AIS data for that date/region; run the full pipeline end-to-end and compare its output against the known outcome

2. **Case 2 — Chennai oil spill (January 2017, LPG tanker collision near Ennore/Kamarajar Port):** same process — gather documented details, pull matching satellite/AIS data, run the pipeline, compare against the known outcome

3. **Document results honestly:** how close did the origin heatmap come to the actual spill site? Did the attribution engine correctly rank the known responsible vessel(s) highly? Where did it fall short, and why (be upfront about this — it strengthens credibility rather than undermining it)

4. **Note before committing full time here:** confirm Sentinel-1/AIS archival data is actually accessible for these specific historical dates before building your validation slide around them — verify this early in the phase, not the night before the pitch

**Git handling:** No new module — this phase runs the merged `main` branch pipeline. Log results in `docs/validation_results.md`.

---

### PHASE 9 — Pitch Assembly
**Owner:** Whole team, assembled by Person 6 (or whoever leads presentation)

**Research paper integrated:**
- Recent oil-spill change-detection literature notes that most existing detection methods rely on single-static-image segmentation, which struggles against visually similar oceanic features and has limited generalizability — a strong framing line for your "gap in current approaches" slide

**Deep steps:**

1. Build the "We Read The Literature" slide — explicitly name: Suez Canal regional fine-tuning study, SAR-UV wind-integrated false-positive suppression (with the 89.4%/83.4%/85.7% stats), bidirectional drift methodology, AIS coastal security research, XAI-based evidence design
2. Open the live demo with a real historical case (Haldia or Chennai), not a synthetic one
3. State plainly what's established science (detection) vs. your actual closed gap (attribution + evidence + dark-vessel handling)
4. Deliberately demo a "why NOT this vessel" moment and, if it occurs naturally in your validation run, an "insufficient evidence" outcome — these signal system maturity
5. Prepare answers for the two hardest likely judge questions: "why not just use existing spill-detection tools?" (answer: they stop at detection; we built the full attribution chain) and "how confident are you in the drift model's accuracy?" (answer: honestly state your Phase 8 validation results, including limitations)

---

## 4. FULL FOLDER STRUCTURE (reference — set up in Phase 0)

```
sih26143-oil-spill-attribution/
├── README.md
├── .gitignore
├── requirements.txt
├── data/
│   ├── raw/ (Phase 1)
│   ├── processed/ (Phase 1)
│   ├── labeled/ (Phase 1) → images/, masks/
│   └── validation_cases/ (Phase 8)
├── models/
│   ├── detection/ (Person 1 — Phase 1)
│   ├── false_positive_filter/ (Person 2 — Phase 2)
│   ├── drift_model/ (Person 3 — Phase 3)
│   └── attribution_engine/ (Person 5 — Phase 5)
├── backend/
│   ├── api/ (Person 6 — integration)
│   ├── ais_pipeline/ (Person 4 — Phase 4)
│   ├── evidence_engine/ (Person 5 — Phase 6)
│   └── report_generator/ (Person 6 — Phase 7 stretch)
├── frontend/
│   ├── dashboard/ (Person 6 — Phase 7)
│   └── components/
├── notebooks/ (experimentation — anyone)
├── docs/
│   ├── problem_statement.md
│   ├── research_notes.md
│   ├── build_checklist.md (this document)
│   ├── validation_results.md (Phase 8)
│   └── pitch_deck/
├── tests/
└── scripts/
    ├── tile_dataset.py (Phase 1)
    └── run_pipeline.py (end-to-end demo runner)
```

---

## 5. SCOPE PRIORITY (if time runs short)

**Must-have (build first, in this order):** Phase 0 → Phase 1 → Phase 2 → Phase 3 (backward drift only) → Phase 4 (AIS correlation only) → Phase 5 → Phase 8

**Differentiators (add once core works):** Bidirectional drift (Phase 3), origin heatmap (Phase 3), evidence chain + why-not-vessel (Phase 6)

**Stretch/wow (only if time allows):** Dark-vessel detection (Phase 4), behavioral anomaly scoring (Phase 4), Time Machine slider (Phase 7), auto-generated PDF report (Phase 7)
