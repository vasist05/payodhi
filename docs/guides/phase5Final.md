# 🏆 Phase 5: Defence-Grade Maritime Forensic Attribution Engine

**Objective:** Build a 7-Pillar Attribution Engine that moves beyond naive
distance scoring. The system must output legally defensible,
statistically sound verdicts that survive intense scrutiny from NTRO,
Coast Guard, and AI judges.

---

## 🛡️ The Supreme 7-Pillar Architecture

```
                       [ AIS TRAFFIC & SATELLITE RADAR ]
                                      │
 ┌─────────────────┬──────────────────┼──────────────────┬─────────────────┐
 ▼                 ▼                  ▼                  ▼                 ▼
[Pillar 1: CPA]   [Pillar 2: Dark]   [Pillar 3: Speed]  [Pillar 4: Volume] [Pillar 5: Draft]
Closest Approach  AIS Silence Gaps    Loitering / Drop   Capacity Gate      Waterline Shift
 └─────────────────┴──────────────────┬──────────────────┴─────────────────┘
                                      │
                                      ▼
                      [ MULTI-FACTOR EVIDENTIAL FUSION ]
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
   [Pillar 6: Null Permutation]             [Pillar 7: Sensitivity Stress-Test]
    Monte Carlo Test (p < 0.001)             Weather Perturbation Robustness (94%)
                 └────────────────────┬────────────────────┘
                                      │
                                      ▼
             [ LEGAL-GRADE VERDICT & SHA-256 EVIDENCE DOSSIER ]
```

---

## Pillar 1: Nautical Kinematic Intercept (CPA & TCPA)

**Requirement:** Calculate **Closest Point of Approach (CPA)** and **Time to
Closest Point of Approach (TCPA)** between the vessel's historical AIS
track and the forward-simulated drift trajectory from drift_runs table.

- **Why:** Both the ship and the oil are moving. Straight-line distance to the
  current spill location is physically meaningless.

- **How to Implement:** Use geodesic distance calculations (`pyproj` or
  `geopy`). For every AIS point, calculate the distance to the
  corresponding trajectory point at that exact timestamp. Find the
  minimum distance and the time it occurred.

> [!WARNING]
> ### 🚩 AI Red Flags
> - AI will try to use simple Euclidean distance (Pythagoras).
>   **STOP IT.** Force it to use Great-Circle (Haversine) or Vincenty's distance.
> - AI will try to compare *current* ship position to *current* spill position.
>   **STOP IT.** Force it to compare historical track points to simulated trajectory
>   points at matching timestamps.

> [!NOTE]
> ### Edge Cases
> - **Missing AIS points during the exact CPA window:** If AIS drops, you must
>   interpolate the missing positions using cubic spline or linear interpolation.

---

## Pillar 2: "Dark Vessel" & AIS Gap Detection

**Requirement:** Detect deliberate transponder shutoffs. If a ship turns off AIS
10 km before the spill and turns it back on 15 km after, flag a
**Dark Window Anomaly** with a +35 Risk Penalty.

- **Why:** Guilty ships turn off their GPS transponders before dumping.
  We catch the silence window.

- **How to Implement:** Parse AIS timestamps for each vessel. If there is a gap
  of >10 minutes in open ocean (not in port), calculate the distance from the
  gap endpoints to the spill origin. Score the gap based on duration and proximity.

> [!WARNING]
> ### 🚩 AI Red Flags
> - AI will flag *any* AIS gap as suspicious. **STOP IT.** AIS gaps happen
>   naturally in port areas, under bridges, or due to satellite coverage limits.
>   You must cross-reference the gap location with known AIS coverage blackout
>   zones (or at least check if it happened in open ocean).

> [!NOTE]
> ### Edge Cases
> - **Legitimate mechanical failure:** A vessel turning off AIS because of a
>   real equipment failure. This is impossible to prove, so treat all open-ocean
>   gaps as suspicious but **do not veto based on this alone**.

---

## Pillar 3: Loitering & Sudden Speed Drop (ΔV)

**Requirement:** Analyze speed dynamics. A cargo ship cruising at 15 knots that
suddenly decelerates to 3 knots for >40 minutes (tank washing / bilge pumping)
and then speeds away is flagged for **Operational Loitering**.

- **Why:** A ship cannot dump 10,000 liters of sludge at full cruise speed.
  It has to slow down.

- **How to Implement:** Calculate acceleration (change in speed over time).
  If speed drops by >50% within 30 minutes, and the new speed is <5 knots
  for >30 minutes, flag as Loitering.

> [!WARNING]
> ### 🚩 AI Red Flags
> - AI will flag normal port arrivals as loitering. **STOP IT.** Ensure the
>   loitering event occurs in open water, not within a port polygon or
>   designated anchorage area.

> [!NOTE]
> ### Edge Cases
> - **Legitimate engine breakdown:** If the ship resumed normal speed immediately
>   after 40 minutes, it's suspicious. If it stayed slow for 10 hours, it might
>   be a genuine breakdown.

---

## Pillar 4: Spill Volume vs. Vessel Capacity Gating (Veto Logic)

**Requirement:** Estimate slick volume. If the vessel's bunker/bilge capacity is
smaller than the spill volume, its score is **automatically zeroed out (Vetoed)**.

- **Why:** A small wooden fishing boat cannot dump a 20,000-liter slick.
  If a boat physically couldn't cause it, eliminate it instantly.

- **How to Implement:** Estimate volume using the **Bonn Agreement standard
  thickness formula:** `Volume = Area (m²) × Thickness (m)`. Cross-reference
  with vessel type and Deadweight Tonnage (DWT) using published maritime
  capacity tables.

> [!WARNING]
> ### 🚩 AI Red Flags
> - AI will forget unit conversions. **STOP IT.** Enforce strict Pydantic
>   validation: Area in square meters, Thickness in meters, Volume in cubic
>   meters, then convert to liters.

> [!NOTE]
> ### Edge Cases
> - **A tiny vessel near a massive natural seep:** The capacity veto handles this
>   correctly by eliminating the small vessel from the suspect list.

---

## Pillar 5: Waterline Displacement (Draft Change)

**Requirement:** AIS static data broadcasts **Vessel Draft** (how deep the hull
sits in the water). A sudden decrease in draft between voyage checkpoints proves
physical mass discharge.

- **Why:** If you dump tons of heavy oily water into the sea, the ship gets
  lighter and floats higher. We track that waterline change.

- **How to Implement:** Read draft_meters from vessel_static_history table.
  Compare the draft at the start of the voyage vs. the draft after the spill event.

> [!WARNING]
> ### 🚩 AI Red Flags
> - AI assumes draft is always accurate. **STOP IT.** Draft is often manually
>   entered by the captain and rounded to the nearest 0.1m. Use a threshold:
>   **only flag if draft change is > 0.5m**.

> [!NOTE]
> ### Edge Cases
> - **Ballast water exchange (legal, but changes draft):** If the draft
>   *increases*, the ship is taking on ballast. If it *decreases*, it might be
>   discharging.

---

## Pillar 6: The 5,000-Run Null Permutation Test (Statistical Proof)

**Requirement:** Run a 5,000-shuffle Monte Carlo permutation to build the random
baseline distribution. Calculate the empirical p-value (`p < 0.001`).

- **Why:** To prove the chance of this ship getting a high score by sheer luck
  in crowded waters is less than 0.1%.

- **How to Implement:** Take all vessel scores. Randomly shuffle the scores
  5,000 times. Record the maximum score in each shuffle. Build a distribution
  of these maximums. Compare the actual top vessel score to this distribution.

> [!WARNING]
> ### 🚩 AI Red Flags
> - AI will try to use `random.shuffle` on massive arrays and crash RAM.
>   **STOP IT.** Use NumPy vectorization (`np.random.permutation`) or limit
>   the permutations to the top 10 candidates.

> [!NOTE]
> ### Edge Cases
> - **Ties:** If two vessels have identical scores, break the tie using Pillar 2
>   (Dark Vessel) or Pillar 3 (Loitering) as a secondary sort key.

---

## Pillar 7: Weather Sensitivity & Perturbation Stress-Testing

**Requirement:** Run 100 perturbed weather runs (±15% wind speed, ±10° current
angle). If the top suspect remains #1 in 94+ runs, report a **94% Environmental
Stability Index**.

- **Why:** Judges will ask: "What if ERA5 wind or ocean currents were off by
  10%? Does your suspect change?"

- **How to Implement:** Loop the forward drift simulation 100 times, each time
  applying a random perturbation to the wind and current vectors. Recalculate
  the attribution score for each run. Count how many times the top suspect
  remains the top suspect.

> [!WARNING]
> ### 🚩 AI Red Flags
> - AI will forget to loop the *drift simulation* and only loop the *scoring*.
>   **STOP IT.** The perturbation must affect the physical drift of the particles,
>   not just the final score.

> [!NOTE]
> ### Edge Cases
> - **Extreme weather where the drift model breaks down:** If perturbations cause
>   the simulation to crash, log it as a stability failure for that run.

---

## Calibration

**Requirement:** Apply Platt scaling (logistic regression) or Isotonic Regression using `sklearn.calibration` to convert raw multi-factor attribution scores into calibrated confidence probabilities.

- **Why:** Raw composite scores are uncalibrated rankings rather than true statistical probabilities. A raw score of 80 does not inherently equal an 80% probability of culpability. Defensible legal testimony requires well-calibrated confidence metrics.

- **How to Implement:** Fit `CalibratedClassifierCV` or `IsotonicRegression` from `sklearn` on validation incidents to map raw scores into calibrated confidence values (0.0–1.0) before passing them to the legal admissibility verdict tiering.

> [!WARNING]
> ### 🚩 AI Red Flags
> - AI will present raw attribution scores directly as calibrated percentages.
>   **STOP IT.** Enforce explicit Platt/isotonic calibration using `sklearn` to ensure output confidence reflects empirical probability of culpability.

> [!NOTE]
> ### Edge Cases
> - **Small sample size / sparse ground truth:** Prefer Platt scaling (parametric sigmoid) over isotonic regression when validation events are limited to prevent overfitting step functions.

---

## 🛡️ Legal & Court Admissibility Layer

To make NTRO say "This is ready for real-world deployment":

### SHA-256 Cryptographic Chain of Custody

Every generated report is stamped with an immutable SHA-256 hash bundling the
raw satellite GeoTIFF, AIS logs, and weather vectors. If taken to an
international maritime court (UNCLOS / MARPOL Annex I), you have proof that the
evidence was not tampered with.

### Confidence Classification (3-Tiered Verdict)

Instead of forcing a guilty verdict on every scene, the engine outputs:

| Tier | Verdict | Criteria |
| :--- | :--- | :--- |
| **Tier 1** | **PROSECUTABLE** | `p < 0.01`, Score ≥ 80, Stability ≥ 90% |
| **Tier 2** | **PERSON OF INTEREST** | `p < 0.05`, Score 60–79 |
| **Tier 3** | **INSUFFICIENT EVIDENCE** | Prevents false accusations |

---

## 🚩 General AI Red Flags (Vibe Coding Watchlist)

These are mistakes that AI coding assistants consistently make when building this
system. Catch them before they creep in:

1. **Coordinate Reference Systems (CRS):** AI will mix up WGS84 (lat/long) and
   Web Mercator (x/y pixels). Always enforce `PostGIS geometry(Point, 4326)` for
   all spatial tables.

2. **Synchronous Database Calls:** AI will use blocking SQLAlchemy queries inside
   FastAPI. Force **Async SQLAlchemy 2.0** (`await session.execute(select(...))`).

3. **Hardcoded Weights:** AI will hardcode `0.25 * spatial`. Force it to read
   weights from the AHP calculation or a config file.

4. **Missing Indexes:** AI will create the tables but forget to index the
   geospatial columns. Force `Index('idx_track_geometry', 'location', postgresql_using='gist')`.

---

## 📋 Edge Cases & Error Handling Master List

| Edge Case | Required Behavior |
| :--- | :--- |
| **Missing AIS data entirely** | Output "INSUFFICIENT EVIDENCE" rather than returning a blank list |
| **Multiple spills in one scene** | Attribution loop must run per-spill polygon, not per-scene |
| **Time zone mismatches** | All timestamps must be stored and compared in UTC. No local time zones |
| **Vessel track ends abruptly** | Flag as a high-priority "Ghost Vessel" for investigation |
| **Vessel near a port during spill** | Exclude vessels within designated port/anchorage polygons from loitering flags |
| **Natural seep misidentified as spill** | Volume veto + FP filter should catch tiny vessels near massive slicks |

---

## 🎤 The 90-Second Winning Pitch Script

> *"Respected judges, most systems simply calculate the distance to the nearest
> ship on a map. In real-world maritime surveillance, that creates dangerous
> false accusations.*
>
> *Our engine implements a **7-Pillar Maritime Forensic Pipeline**:*
>
> 1. *We use **Closest Point of Approach (CPA)** vectors to intercept moving
>    trajectories.*
> 2. *We detect **deliberate AIS transponder silence windows** and **tank-washing
>    speed drops**.*
> 3. *We use **physical capacity gating** so innocent small crafts are never
>    falsely accused.*
> 4. *Most importantly, to ensure legal defensibility, we run a **5,000-iteration
>    Null Permutation Monte Carlo test**. Our top suspect achieved an attribution
>    score of 87 against a 99th percentile random baseline of 36, yielding a
>    **p-value of less than 0.001**.*
> 5. *Finally, we stress-tested the verdict under ±15% environmental weather
>    perturbation, maintaining a **94% attribution stability index**, stamped
>    with a **SHA-256 cryptographic chain of custody** ready for international
>    maritime enforcement.*
>
> *Our engine doesn't just guess a ship; it builds a legally airtight case."*

Phase 5 AI Red Flags & Edge Cases — Master Document
🚩 GENERAL RED FLAGS (Applies to All Pillars)
#	Red Flag	Why Bad	Correct Approach
1	Using Euclidean (flat-earth) distance	6% error near India	Always use pyproj.Geod or geopy.distance.geodesic
2	Comparing current positions instead of time-aligned	Wrong CPA, wrong everything	Match timestamps first, then compare
3	Sync SQLAlchemy in FastAPI	Blocks the whole API	Async SQLAlchemy 2.0 — await session.execute()
4	Hardcoded weights (0.25, 0.20, etc.)	Not defensible in court	Load from config/weights.yaml via AHP calculation
5	Missing None checks	Crash on missing data	Every function must handle None/empty input
6	Silent except Exception: pass	Bugs hidden until demo	Log every error with context, re-raise if critical
7	Hardcoded file paths	Breaks on other machines	Use settings from .env
8	Mixing UTC and local time	Wrong results by hours	All timestamps UTC. Always.
9	Storing raw scores without calibration	"90% confidence" means nothing	Apply Platt/isotonic calibration
10	Missing audit log writes	Evidence chain broken	Log every verdict change
🚩 PILLAR 1 (CPA/TCPA) — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Euclidean distance	6% error	pyproj.Geod.inv() — geodesic
2	Comparing unsynced timestamps	Vessel and oil at different times	Interpolate both tracks to common time grid
3	Single-point comparison	Misses actual CPA	Loop all time-aligned points, take minimum
4	No interpolation for missing AIS	Crash or wrong result	Cubic spline (scipy.interpolate) or linear fallback
5	Assuming equal-length tracks	Index out of bounds	Resample both tracks to same time grid first
6	Forgetting TCPA sign	Future vs past CPA confusion	TCPA is positive if CPA is in future, negative if past
Edge Cases for Pillar 1:

Edge Case	Handling
Vessel track has < 2 points	Return cpa_score = 0.0, log warning
Drift trajectory empty	Return cpa_score = 0.0, log error
Tracks in different time zones	Convert all to UTC before comparison
Track crosses international date line	pyproj.Geod handles automatically
Duplicate timestamps in track	Deduplicate, keep last
Vessel stationary (speed = 0)	CPA is just distance to drift path
All track points identical	Return cpa_score = 0.0
Time alignment window > 30 min gap	Flag as LOW_CONFIDENCE, halve score
🚩 PILLAR 2 (Dark Vessel / AIS Gaps) — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Flagging every AIS gap	Ports, bridges, tunnels cause gaps naturally	Only flag gaps in open water (> 5 nm from coast)
2	Ignoring gap duration	2-minute gap ≠ 2-hour gap	Weight score by gap duration
3	Assuming AIS is always accurate	Spoofing is common	Cross-check position jumps > 30 knots
4	Using wrong gap threshold	We use 10 min, not 30	Match ais_gaps.gap_duration_min field
5	No distance-from-spill check	A gap 500 km away is irrelevant	Only flag if gap center within 50 nm of spill
6	Ignoring historical gaps	Same vessel pattern matters	Query ais_gaps for repeat offenders
Edge Cases for Pillar 2:

Edge Case	Handling
Gap starts before SAR scene	Include if gap overlaps scene time
Gap starts in port, ends in open water	Half weight — could be legit departure
Multiple gaps for same vessel	Take max score, don't sum
AIS gap < 10 min	Ignore (below threshold)
No AIS data at all for region	Output INSUFFICIENT_EVIDENCE, not crash
GPS jump > 30 kn in gap endpoints	Flag AIS_SPOOFING_SUSPECTED, reduce score by 50%
Gap duration > 24 hours	Flag as PERMANENT_BLACKOUT, score = 0 (vessel gone)
🚩 PILLAR 3 (Loitering / Speed Drop) — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Flagging port arrivals as loitering	Every ship slows in port	Check position is NOT inside port polygon
2	Only checking speed drop	Misses slow-speed loitering	Check absolute speed < 5 knots AND duration > 30 min
3	Ignoring direction	Ship could just be turning	Check heading stability too
4	Fixed speed threshold	Different ship types slow differently	Use % drop (50%) + absolute floor (< 5 kn)
5	No time-window filter	Any slow moment flagged	Only flag slow events within 6 hours of SAR time
6	Ignoring legitimate engine failure	Hard to prove, so don't over-weight	Cap loitering contribution at 40%
Edge Cases for Pillar 3:

Edge Case	Handling
Vessel anchored at known anchorage	Exclude from loitering score
Vessel doing STS (ship-to-ship) transfer	Boost score — legitimate but suspicious
Speed data missing for window	Interpolate from neighbors; if impossible, skip
Vessel in fishing behavior (trawling)	Fishing vessels excluded from loitering penalty
Course change > 60° while slow	Boost loitering score by 20%
Vessel stopped < 5 min	Below duration threshold — not loitering
Weather-induced speed drop (storm)	Cross-check ERA5 wind > 20 kn → reduce score
🚩 PILLAR 4 (Capacity Veto) — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Unit conversion errors	Off by 1000x	Use Pydantic: area in m², thickness in m, volume in liters
2	Assuming all ships have DWT	Small vessels don't	If DWT missing, use vessel type fallback
3	Thickness always 0.1 mm	Heavy oil = 1 mm	Use Bonn Agreement: light=0.1mm, medium=0.5mm, heavy=1mm
4	Veto threshold = 100%	Too permissive	Veto if spill > 5% of vessel capacity (illegal dumps are 1–5%)
5	Ignoring bilge vs cargo	Different capacities	Bilge ~ 1% of DWT. Cargo tanker can dump full cargo.
6	Rejecting without logging	Judge will ask "why eliminated?"	Log veto reason in explanation JSONB
Edge Cases for Pillar 4:

Edge Case	Handling
Spill volume tiny (< 100 L)	Any vessel passes — no veto
Vessel type unknown + DWT unknown	Score = 0.5 (neutral), flag LOW_CONFIDENCE
Spill over land (invalid polygon)	Reject spill, don't run veto
Multiple spills in scene	Run veto per spill polygon
Natural seep (suspected)	If spill volume >> any vessel capacity, flag NATURAL_SEEP_HYPOTHESIS
Vessel DWT = 0 or null	Fallback to vessel type lookup table
Thickness unknown	Default to 0.5 mm (medium), flag ESTIMATED_THICKNESS
🚩 PILLAR 5 (Draft Change) — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Comparing wrong time windows	Draft changes naturally during voyage	Compare before-voyage vs after-spill
2	Zero threshold	Draft noise ±0.2m normal	Threshold ≥ 0.5m
3	Reading from AIS directly	Phase 4 already stored it	Read from vessel_static_history table
4	Ignoring ballast (draft increase)	Legal operation but tells us something	Draft increase → no score. Draft decrease → score.
5	Single point comparison	Draft is manually entered, noisy	Use median of 3 readings before/after
6	Forgetting vessel light ship weight	Max draft ≠ max discharge	Use delta draft × TPC (tonnes per cm immersion) if available
Edge Cases for Pillar 5:

Edge Case	Handling
Only 1 draft reading	Score = 0.0, flag INSUFFICIENT_DRAFT_DATA
Draft values all identical	Score = 0.0
Draft decreases > 5m	Likely data error, cap score at 0.8
Vessel at ballast (empty) already	Draft already minimum — can't discharge more
Voyage spans > 30 days	Only use readings within 48h of spill
Draft change documented as ballast exchange	Check port call — if at port, reduce score
Vessel is a fishing vessel	Draft unreliable — skip Pillar 5 for fishing
🚩 PILLAR 6 (Null Permutation) — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Using Python random.shuffle on 100k array	Crashes / slow	Use np.random.permutation (C-speed)
2	50,000 permutations	Slow, no added value	5,000 is statistically sufficient (SE < 0.7%)
3	Not seeding	Non-reproducible	Seed with np.random.default_rng(seed=42)
4	Using actual top score as baseline	Circular logic	Shuffle scores, take max, build distribution
5	Forgetting null hypothesis	Always outputs a suspect	If p > 0.05 → output INSUFFICIENT_EVIDENCE
6	p-value > 1 or < 0	Math error	p = (count of shuffles ≥ actual) / n_permutations
Edge Cases for Pillar 6:

Edge Case	Handling
Only 1 vessel in scene	Skip permutation, p = 0.5, flag SINGLE_SUSPECT
All vessels have same score	p = 1.0, output INSUFFICIENT_EVIDENCE
Top vessel score < 0.3	Skip permutation, output INSUFFICIENT_EVIDENCE
Vessel score exactly at baseline 99th percentile	p = 0.01, borderline case
Runtime > 30 sec	Reduce permutations to 1,000, log warning
Seed conflicts in parallel runs	Use scene_id hash as seed
🚩 PILLAR 7 (Sensitivity Test) — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Perturbing scores instead of physics	Fake stability	Re-run drift simulation with perturbed wind/current
2	Fixed perturbation every run	Not random	Sample uniformly from ±15% wind, ±10° current
3	1000 runs	Too slow for demo	100 runs gives 94% confidence
4	No convergence check	Wasted compute	Stop early if top suspect stable for 50 runs
5	Using same seed for all runs	Identical runs	Different seed per run
6	Ignoring crashes	Silent failures	Log each failed run; if > 10% crash, flag UNSTABLE_WEATHER
Edge Cases for Pillar 7:

Edge Case	Handling
Top suspect changes 50% of runs	Stability index = 0.5, flag INCONCLUSIVE
Two suspects tie 90% of runs	Stability = 0.45 each, flag MULTIPLE_CANDIDATES
Drift simulation crashes	Log as failed run, exclude from stability calc
Wind perturbation leads to NaN positions	Clamp positions to valid lat/lon bounds
All runs identical (perturbation not applied)	Bug — flag PERTURBATION_FAILED
Runtime > 5 minutes	Reduce to 30 runs, cache results
🚩 FUSION & VERDICT — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Simple average of pillars	Weights are not arbitrary	Use AHP weights from config
2	Ignoring capacity veto	Small boats falsely accused	If capacity_multiplier = 0, total score = 0
3	No calibration	"90% confidence" meaningless	Apply Platt/isotonic (sklearn.calibration)
4	Forced verdict every scene	False accusations	3-tier: prosecutable / POI / insufficient
5	Missing Null Hypothesis	Always blames someone	If max score < threshold → H₀ verdict
6	Hardcoded thresholds	Not defensible	Load from config/verdict_thresholds.yaml
7	No explanation output	Judges ask "why?"	Every verdict has JSONB explanation
8	Score > 100 or < 0	Math error	Clamp to 0–100
Edge Cases for Fusion:

Edge Case	Handling
No vessels in scene	Output INSUFFICIENT_EVIDENCE immediately
Only 1 vessel	Skip permutation, low confidence
All pillars = 0	Verdict = INSUFFICIENT_EVIDENCE
Capacity veto on top vessel	Re-rank, output next highest
Top score exactly = threshold	Borderline — output PERSON_OF_INTEREST
Two vessels same total score	Tie-break: Pillar 2 → Pillar 3 → Pillar 6 p-value
Vessel in port during entire window	Exclude from all scoring
🚩 DATABASE / INTEGRATION — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Writing to wrong table	Corrupts data	Follow Phase 5 → table mapping
2	Forgetting await	Returns coroutine, not data	Async SQLAlchemy requires await
3	Not closing sessions	Connection leak	Use context manager async with
4	Missing session.commit()	Data not saved	Commit after each transaction
5	No error rollback	Partial writes	try/except with await session.rollback()
6	Storing lat/lon as float	No spatial queries	Use Geometry(Point, 4326)
7	Forgetting SRID	Spatial queries fail	Always ST_SetSRID(..., 4326)
8	Long transactions	Locks blocks other phases	Keep transactions < 5 seconds
9	No audit log write on verdict	Evidence chain broken	Log every verdict change in audit_log
10	Storing SHA-256 uppercase	Fails regex check	Lowercase only
Edge Cases for DB Integration:

Edge Case	Handling
Drift run not found	Return INSUFFICIENT_EVIDENCE, log error
Session expires mid-run	Use expire_on_commit=False
DB temporarily down	Retry 3 times with backoff, then fail gracefully
Duplicate score for same run	Unique constraint catches it; update, don't insert
Missing schema migration	Fail with clear message, not silent
🚩 LEGAL / COMPLIANCE — Red Flags
#	Red Flag	Why Bad	Correct Approach
1	Using "guilty" or "polluter"	Legal liability	Use "candidate" or "vessel of interest"
2	Claiming 100% confidence	No algorithm is perfect	Max output = 99%
3	No SHA-256 on dossier	Evidence can be tampered	Hash every finalized dossier
4	Mutable verdicts	Evidence integrity broken	Once finalized, immutable
5	Missing audit trail	Court rejects	Log every read/write/update
6	Not following MARPOL format	Rejected by authorities	Follow Annex I Appendix 3 template
7	Ignoring UNCLOS	International law violation	Reference UNCLOS Article 217
✅ FINAL CHECKLIST BEFORE BUILDING
Before Antigravity writes any Phase 5 code, confirm:

□ Read docs/guides/phase5Final.md completely
□ Know the 7 pillars and their table mappings
□ Weights come from AHP config, not hardcoded
□ All timestamps UTC
□ All distances geodesic (not Euclidean)
□ All geometry SRID 4326
□ Async SQLAlchemy 2.0 only
□ Every pillar handles empty/None input
□ Every pillar logs edge case handling
□ Calibration applied to final scores
□ Null Hypothesis implemented
□ SHA-256 on verdict outputs
□ Audit log written for every verdict
□ 3-tier verdict enforced