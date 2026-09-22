# Walkthrough: Phase 2 ↔ Database & Backend Integration

We have integrated the Phase 2 False-Positive Filter with PostgreSQL/TimescaleDB and FastAPI adhering to the database contracts in `docs/guides/DataBaseFinal.md`.

---

## 1. Summary of Changes

### Rebase Target: `core/phase2_false_positive/`
- Full Phase 2 ML package organized in [`core/phase2_false_positive/`](../core/phase2_false_positive/):
  - `dataset.py`, `evaluate.py`, `inference.py`, `model.py`, `requirements.txt`, `train.py`.
  - Checkpoints: `best_model_sar_only.pth`, `best_model_sar_speed.pth`, `best_model_sar_uv.pth`, `csiro_classifier.joblib`.

### Database Schema Contracts (`docs/guides/DataBaseFinal.md`)
- **`spills` (Table 4)**: Strictly 14 columns matching Table 4.
  - Zero banned columns: No `wind_u10`, `wind_v10`, `wind_speed`, or `rejection_reason` in `spills`.
  - Rejection rationale, model explanation, and lookalike details persist in `review_notes`.
- **`scenes` (Table 3)**:
  - Scalar `wind_speed` and `wind_direction` persist in `scenes`.
  - Directional components $U_{10}$ and $V_{10}$ are dynamically derived on read in [`SceneResponse`](../backend/app/schemas/scene.py) via `@computed_field`.
- **`audit_log` (Table 8)**:
  - Singular table name `audit_log`.
  - Append-only repository with SHA-256 hash chaining (`event_hash = sha256(prev_hash + payload)`).

### Service Layer: 3-Tier Hybrid Wind Resolution
In [`FilterService`](../backend/app/services/filter_service.py):
1. **Tier 1 (Scene-derived):** Computes $u_{10} = \text{speed} \cdot \sin(\text{rad}(\text{direction}))$, $v_{10} = \text{speed} \cdot \cos(\text{rad}(\text{direction}))$, tagged `"scene_derived"`.
2. **Tier 2 (Historical CSIRO fallback):** Resolves exact $(u_{10}, v_{10})$ vector from `data/fp_filter/wind_metadata.json`, tagged `"metadata_json"`.
3. **Tier 3 (None):** Default `(None, None)`, tagged `"none"`.
- Per-candidate error isolation: Individual patch errors are caught into `failed: list[dict]`, allowing valid candidates to be committed transactionally.

### API & Alembic
- **Routers**:
  - `POST /api/v1/spills/filter`: Pinned batch response shape (`confirmed`, `rejected`, `failed`, `model_mode`, `calibration_temperature`).
  - `GET /api/v1/spills` & `GET /api/v1/spills/{id}`: Spills query with eager-loaded scene wind context.
  - `GET /health`: Async health checks for DB, Redis, MinIO.
- **Alembic Forward Migration**:
  - Created [`c72b10a90df1_align_spill_polygon_index.py`](../backend/alembic/versions/c72b10a90df1_align_spill_polygon_index.py) to ensure `idx_spills_polygon` GiST index is present without modifying applied historical migrations.

---

## 2. Verification Results

### Unit & Contract Tests
Executed [`tests/test_phase2_db_integration.py`](../tests/test_phase2_db_integration.py):
```
Ran 5 tests in 6.984s
OK
```
1. `test_geojson_wkt_conversion`: PostGIS MultiPolygon WKT conversion verified.
2. `test_scene_derived_wind_components`: Dynamic $U_{10}/V_{10}$ math verified.
3. `test_spill_table_contract_and_no_banned_columns`: Exactly 14 columns, 0 banned columns verified.
4. `test_pinned_batch_response_shape`: `confirmed`, `rejected`, `failed`, `model_mode`, `calibration_temperature` verified.
5. `test_filter_service_hybrid_wind_resolution`: 3-tier wind resolution verified.

### Model Inference Benchmark
Tested against benchmark patches:
- **True Oil Spill** (`0_0_0_img_0bBRglmdLdC6cFxF_JAV_cls_1.jpg`):
  - Result: `is_oil: True`, `confidence: 0.9234` (92.34% mineral oil spill confirmed)
  - Source: `PyTorch SAR-UV ResNet18`, temperature scaled ($T = 1.3788$)
- **Lookalike Non-Oil** (`0_0_0_img_01RNDdyOUhULo97s_SFr_cls_0.jpg`):
  - Result: `is_oil: False`, `confidence: 0.00072` (0.07% lookalike decisively rejected)
  - Wind provenance: Tier 2 fallback automatically resolved $(u_{10} = 6.158, v_{10} = -8.267)$
