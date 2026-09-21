# Payodi Database Engineering Guide

## 1. Purpose and Scope

This database stores everything Payodi needs to detect oil spills, identify the responsible vessel, and produce court-admissible evidence.

It stores:
- Ship identities and GPS tracks (AIS data)
- Satellite scenes and their metadata
- Detected oil spill polygons
- Forward-drift simulation runs
- 7-Pillar attribution scores and verdicts
- Legal dossiers with SHA-256 hashes
- Immutable audit trail

Database design comes before Phase 4 because every later phase reads and writes to it. Get this wrong, and Phase 4, 5, and 6 will all be unstable.

**In scope:**
- 12 tables covering vessel, track, scene, spill, drift, attribution, dossier, audit, ais_gaps, cpa_events, environmental_data, jobs
- TimescaleDB hypertable for tracks
- PostGIS spatial indexing
- Alembic migrations
- MinIO object storage integration
- Role-based access control (RLS)

**Out of scope (first release):**
- Real-time streaming replication
- Multi-region failover
- Data lake analytics
- ML feature store

**Definition of done for database Phase 1:**
- All 12 tables exist with constraints
- TimescaleDB hypertable created for tracks
- PostGIS indexes on all geometry columns
- Alembic migrations run cleanly on fresh DB
- Test workflow (vessel → track → scene → spill → drift → score → dossier) works end-to-end
- Audit log is append-only (app role cannot UPDATE/DELETE)
- MinIO bucket connected and tested

---

## 2. Final Technology Decisions

| Decision | Choice | Reason |
|---|---|---|
| Database | PostgreSQL 16+ | Industry standard, ACID, mature |
| Spatial | PostGIS 3.x | Gold standard for geospatial |
| Time-series | TimescaleDB | AIS tracks are pure time-series, 100x faster range queries |
| Cache/Queue | Redis 7+ | Fast cache + job mirror |
| Object storage | MinIO | S3-compatible, free, runs in Docker |
| Migrations | Alembic | Python-native, works with SQLAlchemy 2.0 |
| Backend | Python FastAPI | Async, fast, Pydantic integration |
| ORM | SQLAlchemy 2.0 async | Non-blocking |
| Validation | Pydantic v2 | Bodyguard for API data |
| Primary keys | UUID v4 | No collision, safe for distributed systems |
| Timestamps | timestamptz (UTC only) | Legal evidence requires UTC |
| Geospatial CRS | EPSG:4326 (WGS84) | Global standard for lat/long |
| Config | Docker Compose | One command runs everything |

**Hard rules:**
- Never store raw satellite image files in the database. Store metadata, SHA-256 hash, URI, timestamps, footprint, processing status only.
- Never rely only on application-side validation. Database enforces critical constraints.
- Use geometry (not geography) with EPSG:4326 for storage. Use geography only for distance queries on small datasets.
- All timestamps in UTC. No local time zones. Ever.

---

## 3. Architecture Overview

### Mermaid ER Diagram

```mermaid
erDiagram
    vessels ||--o{ tracks : "has"
    vessels ||--o{ ais_gaps : "has"
    vessels ||--o{ drift_runs : "tested in"
    vessels ||--o{ cpa_events : "computes"
    scenes ||--o{ spills : "contains"
    scenes ||--o{ drift_runs : "source of"
    scenes ||--o{ dossiers : "generates"
    scenes ||--o{ environmental_data : "has"
    spills ||--o{ drift_runs : "target of"
    drift_runs ||--o{ attribution_scores : "produces"
    drift_runs ||--o{ cpa_events : "produces"
    dossiers }o--|| dossiers : "supersedes"

    vessels {
        uuid id PK
        string mmsi
        string imo
        string vessel_name
        string vessel_type
    }
    tracks {
        uuid id PK
        uuid vessel_id FK
        timestamptz recorded_at
        geometry position
        numeric speed_knots
    }
    ais_gaps {
        uuid id PK
        uuid vessel_id FK
        timestamptz gap_start
        timestamptz gap_end
    }
    scenes {
        uuid id PK
        string external_scene_id
        timestamptz captured_at
        geometry footprint
        string sha256
    }
    spills {
        uuid id PK
        uuid scene_id FK
        geometry spill_polygon
        numeric confidence_score
    }
    drift_runs {
        uuid id PK
        uuid scene_id FK
        uuid vessel_id FK
        string status
        string output_sha256
    }
    cpa_events {
        uuid id PK
        uuid drift_run_id FK
        uuid vessel_id FK
        numeric min_distance_m
    }
    attribution_scores {
        uuid id PK
        uuid drift_run_id FK
        numeric total_score
        string verdict
    }
    dossiers {
        uuid id PK
        uuid scene_id FK
        string sha256
        string status
    }
    audit_log {
        uuid id PK
        timestamptz occurred_at
        string action
        string entity_type
    }
    environmental_data {
        uuid id PK
        string source
        timestamptz valid_time
        geometry location
        numeric value
    }
    jobs {
        uuid id PK
        string job_type
        string idempotency_key
        string status
    }
```

### Mermaid Data Flow

```mermaid
flowchart TD
    AIS[Raw AIS/GPS] --> V[vessels]
    AIS --> T[tracks]
    T --> AG[ais_gaps]
    
    SAT[Satellite Metadata] --> S[scenes]
    SAT --> ED[environmental_data]
    S --> SP[spills]
    
    T --> DR[drift_runs]
    SP --> DR
    S --> DR
    
    DR --> CPA[cpa_events]
    DR --> AS[attribution_scores]
    
    AS --> D[dossiers]
    
    V --> AL[audit_log]
    T --> AL
    S --> AL
    SP --> AL
    DR --> AL
    AS --> AL
    D --> AL
    
    J[jobs] --> DR
    J --> SP
```

**Parent-child relationships:**
- Scene → Spills (one scene, many spills)
- Vessel → Tracks (one vessel, many GPS points)
- Vessel → AIS Gaps (one vessel, many gaps)
- Drift Run → Attribution Scores (one run, one score row per scoring version)
- Drift Run → CPA Events (one run, many vessel CPA results)
- Dossier → Dossier (supersedes chain for corrections)

**Immutable after creation:**
- audit_log (append-only)
- dossiers (once finalized)
- tracks (once inserted, never updated)
- cpa_events (once computed)

**Mutable:**
- vessels (name, type can update)
- scenes (processing_status updates)
- spills (status, reviewed_by, review_notes)
- drift_runs (status transitions)

---

## 4. Database Naming Rules

- **Tables:** snake_case, plural (vessels, tracks, scenes)
- **Columns:** snake_case (vessel_id, recorded_at)
- **Primary key:** always named `id`
- **Foreign keys:** `<table_singular>_id` (vessel_id, scene_id)
- **Timestamps:** created_at, updated_at, deleted_at
- **Enums:** suffix `_enum` (vessel_type_enum, verdict_enum)
- **Indexes:** `idx_<table>_<column>`
- **Constraints:** `chk_<table>_<rule>`, `fk_<table>_<ref>`, `uq_<table>_<column>`
- **Migrations:** `V001__enable_extensions.py` (Alembic style)
- **No reserved words.** No ambiguous names like `data`, `info`, `value`, `status` without context.

---

## 5. Required Tables

### Table 1: vessels

**Purpose:** One row per unique vessel.

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | Primary key |
| mmsi | text | Yes | — | unique when not null | Maritime Mobile Service Identity |
| imo | text | No | null | unique when not null | IMO number |
| vessel_name | text | Yes | — | not unique | Ship name (can change) |
| vessel_type | vessel_type_enum | Yes | 'unknown' | — | Type category |
| flag_country_code | char(2) | No | null | ISO 3166-1 alpha-2 | Flag state |
| deadweight_tonnage | numeric(12,2) | No | null | > 0 | DWT in tonnes |
| source | text | Yes | — | — | 'aisstream', 'gfw', 'manual' |
| metadata | jsonb | No | '{}' | — | Extra source fields |
| created_at | timestamptz | Yes | now() | UTC | |
| updated_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- MMSI unique when present
- Vessel name is not unique
- Validate MMSI is 9 digits
- Vessel name changes: keep the same row, update `vessel_name`, and write audit event.

**Indexes:**
- `idx_vessels_mmsi` (unique partial)
- `idx_vessels_imo` (unique partial)
- `idx_vessels_type`

**Write frequency:** Low
**Read patterns:** Lookup by MMSI, list by type

---

### Table 2: tracks

**Purpose:** GPS position history. TimescaleDB hypertable.

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| vessel_id | UUID | Yes | — | FK → vessels | |
| recorded_at | timestamptz | Yes | — | UTC | AIS timestamp |
| position | geometry(Point,4326) | Yes | — | SRID 4326 | Lat/long |
| speed_knots | numeric(5,2) | Yes | — | >= 0, <= 100 | |
| course_degrees | numeric(5,2) | Yes | — | 0–360 | Direction of motion |
| heading_degrees | numeric(5,2) | No | null | 0–360 | Ship's compass heading |
| navigational_status | text | No | null | — | 'underway', 'anchored', etc. |
| source | text | Yes | — | — | |
| source_record_id | text | Yes | — | — | Idempotency key |
| ingestion_batch_id | UUID | No | null | — | Import batch |
| created_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- Latitude range -90 to 90, longitude -180 to 180 enforced via PostGIS geometry validation.
- Speed >= 0.
- Course/heading in 0–360.
- Unique constraint on `(source, source_record_id)` for idempotent imports.
- **TimescaleDB hypertable on `recorded_at`** (chunk interval: 7 days).

**Indexes:**
- `idx_tracks_vessel_time` (vessel_id, recorded_at DESC)
- `idx_tracks_position` GiST
- `idx_tracks_recorded_at` BRIN (for range scans)

**Write frequency:** Very high (bulk inserts)
**Read patterns:** Time-range by vessel, spatial proximity to spill

---

### Table 3: scenes

**Purpose:** Satellite image metadata.

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| source_provider | text | Yes | — | — | 'CDSE', 'ESA' |
| external_scene_id | text | Yes | — | unique with provider | |
| captured_at | timestamptz | Yes | — | UTC | Acquisition time |
| ingested_at | timestamptz | Yes | now() | UTC | |
| footprint | geometry(Polygon,4326) | Yes | — | valid polygon | Coverage area |
| cloud_cover_percentage | numeric(5,2) | No | null | 0–100 | |
| wind_speed | numeric(5,2) | No | null | >= 0 | Scene average |
| wind_direction | numeric(5,2) | No | null | 0–360 | |
| storage_uri | text | Yes | — | no credentials | MinIO path |
| sha256 | char(64) | Yes | — | hex format | Image hash |
| processing_status | scene_status_enum | Yes | 'pending' | — | |
| source_metadata | jsonb | No | '{}' | — | |
| created_at | timestamptz | Yes | now() | UTC | |
| updated_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- Unique `(source_provider, external_scene_id)`.
- SHA-256 format validation (lowercase hex, 64 chars).
- Storage URI must not contain credentials.
- If metadata incomplete: store row with `processing_status = 'pending_metadata'`.

**Indexes:**
- `idx_scenes_footprint` GiST
- `idx_scenes_captured_at`
- `idx_scenes_provider_external` unique

---

### Table 4: spills

**Purpose:** Detected oil spill polygons.

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| scene_id | UUID | Yes | — | FK → scenes | |
| detected_at | timestamptz | Yes | now() | UTC | |
| spill_polygon | geometry(MultiPolygon,4326) | Yes | — | valid, ST_IsValid | |
| area_sq_km | numeric(10,3) | Yes | — | > 0 | |
| detection_model_name | text | Yes | — | — | |
| detection_model_version | text | Yes | — | — | |
| confidence_score | numeric(4,3) | Yes | — | 0–1 | |
| processing_run_id | UUID | No | null | — | |
| status | spill_status_enum | Yes | 'detected' | — | |
| reviewed_by | text | No | null | — | |
| review_notes | text | No | null | — | |
| created_at | timestamptz | Yes | now() | UTC | |
| updated_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- Original detection never overwritten. Human review adds fields but preserves raw geometry.
- Invalid polygons: reject on insert. Use `ST_MakeValid` before insert.
- Multiple spills in one scene: allowed.

**Indexes:**
- `idx_spills_scene`
- `idx_spills_polygon` GiST
- `idx_spills_status`

---

### Table 5: drift_runs

**Purpose:** Forward-drift simulation runs.

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| scene_id | UUID | Yes | — | FK → scenes | |
| vessel_id | UUID | Yes | — | FK → vessels | |
| spill_id | UUID | No | null | FK → spills | |
| simulation_version | text | Yes | — | — | |
| model_parameters | jsonb | Yes | — | — | Wind, current, diffusion |
| run_fingerprint | char(64) | Yes | — | unique | Idempotency key |
| started_at | timestamptz | Yes | now() | UTC | |
| completed_at | timestamptz | No | null | UTC | |
| status | drift_status_enum | Yes | 'queued' | — | |
| output_storage_uri | text | No | null | — | MinIO path |
| output_sha256 | char(64) | No | null | hex | |
| result_summary | jsonb | No | '{}' | — | |
| error_message | text | No | null | — | |
| created_at | timestamptz | Yes | now() | UTC | |
| updated_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- Failed runs preserved. Never deleted.
- Retry = new row with new fingerprint.
- Status transitions enforced by trigger.

**Indexes:**
- `idx_drift_runs_scene`
- `idx_drift_runs_vessel`
- `idx_drift_runs_fingerprint` unique

---

### Table 6: attribution_scores

**Purpose:** 7-Pillar attribution result per drift run.

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| drift_run_id | UUID | Yes | — | FK → drift_runs | |
| scoring_version | text | Yes | — | — | |
| cpa_score | numeric(4,3) | Yes | — | 0–1 | Pillar 1 |
| dark_vessel_score | numeric(4,3) | Yes | — | 0–1 | Pillar 2 |
| loitering_score | numeric(4,3) | Yes | — | 0–1 | Pillar 3 |
| capacity_multiplier | numeric(4,3) | Yes | — | 0 or 1 | Pillar 4 (0 = veto) |
| draft_change_score | numeric(4,3) | Yes | — | 0–1 | Pillar 5 |
| permutation_p_value | numeric(6,5) | Yes | — | 0–1 | Pillar 6 |
| stability_index | numeric(4,3) | Yes | — | 0–1 | Pillar 7 |
| total_score | numeric(5,2) | Yes | — | 0–100 | Final |
| verdict | verdict_enum | Yes | — | — | 3-tier |
| explanation | jsonb | Yes | — | — | Per-pillar detail |
| calculated_at | timestamptz | Yes | now() | UTC | |
| created_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- All pillar scores 0–1.
- `total_score` computed in **service layer** (Python), not database. Reason: business logic changes frequently, and we want reproducibility tied to `scoring_version`.
- Unique `(drift_run_id, scoring_version)`.
- Verdict values: `prosecutable`, `person_of_interest`, `insufficient_evidence`.

**Indexes:**
- `idx_attribution_run_version` unique
- `idx_attribution_verdict`
- `idx_attribution_total_score`

---

### Table 7: dossiers

**Purpose:** Legal evidence packages.

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| scene_id | UUID | Yes | — | FK → scenes | |
| spill_id | UUID | No | null | FK → spills | |
| dossier_version | text | Yes | — | — | |
| generated_at | timestamptz | Yes | now() | UTC | |
| generated_by | text | Yes | — | — | User/system |
| storage_uri | text | Yes | — | — | MinIO path |
| sha256 | char(64) | Yes | — | hex | |
| evidence_snapshot | jsonb | Yes | — | — | Full state |
| status | dossier_status_enum | Yes | 'draft' | — | |
| supersedes_dossier_id | UUID | No | null | FK → dossiers | |
| created_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- Immutable after `status = 'finalized'`. Enforced by trigger.
- Corrections: new dossier with `supersedes_dossier_id` set.
- SHA-256 mandatory for finalized dossiers.

**Indexes:**
- `idx_dossiers_scene`
- `idx_dossiers_status`

---

### Table 8: audit_log

**Purpose:** Tamper-evident audit trail.

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| occurred_at | timestamptz | Yes | now() | UTC | |
| actor_type | actor_type_enum | Yes | — | — | 'user', 'system', 'ai_agent' |
| actor_id | text | No | null | — | |
| action | audit_action_enum | Yes | — | — | |
| entity_type | text | Yes | — | — | Table name |
| entity_id | UUID | Yes | — | — | |
| request_id | UUID | No | null | — | Correlation |
| ip_address | inet | No | null | — | |
| before_data | jsonb | No | null | — | |
| after_data | jsonb | No | null | — | |
| metadata | jsonb | No | '{}' | — | |
| hash_chain_previous | char(64) | No | null | — | Prior event hash |
| event_hash | char(64) | Yes | — | — | SHA-256 of this event |
| created_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- Append-only. App role cannot UPDATE or DELETE.
- Never log passwords, tokens, secrets, DB URLs.
- Hash chain: `event_hash = SHA256(previous_hash || event_payload)`.

**Indexes:**
- `idx_audit_entity` (entity_type, entity_id)
- `idx_audit_occurred_at`
- `idx_audit_actor`

---

### Table 9: ais_gaps

**Purpose:** Detected AIS transponder silences (Pillar 2).

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| vessel_id | UUID | Yes | — | FK → vessels | |
| gap_start | timestamptz | Yes | — | UTC | Last signal before gap |
| gap_end | timestamptz | Yes | — | UTC | First signal after |
| gap_duration_min | numeric(6,2) | Yes | — | > 0 | |
| last_position | geometry(Point,4326) | Yes | — | — | |
| next_position | geometry(Point,4326) | Yes | — | — | |
| gap_center | geometry(Point,4326) | Yes | — | — | |
| distance_from_coast_nm | numeric(6,2) | No | null | — | |
| is_open_water | boolean | Yes | false | — | |
| created_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- `gap_end > gap_start`.
- Only flag as suspicious if `is_open_water = true`.

**Indexes:**
- `idx_ais_gaps_vessel`
- `idx_ais_gaps_time`
- `idx_ais_gaps_center` GiST

---

### Table 10: cpa_events

**Purpose:** CPA/TCPA results (Pillar 1).

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| drift_run_id | UUID | Yes | — | FK → drift_runs | |
| vessel_id | UUID | Yes | — | FK → vessels | |
| min_distance_m | numeric(10,2) | Yes | — | >= 0 | |
| cpa_timestamp | timestamptz | Yes | — | UTC | |
| tcpa_seconds | numeric(10,2) | Yes | — | — | |
| vessel_position_at_cpa | geometry(Point,4326) | Yes | — | — | |
| slick_position_at_cpa | geometry(Point,4326) | Yes | — | — | |
| created_at | timestamptz | Yes | now() | UTC | |

**Indexes:**
- `idx_cpa_drift_run`
- `idx_cpa_vessel`

---

### Table 11: environmental_data

**Purpose:** ERA5 wind and CMEMS current data.

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| source | text | Yes | — | — | 'ERA5', 'CMEMS' |
| variable | text | Yes | — | — | 'wind_u', 'wind_v', 'current_u', 'current_v' |
| valid_time | timestamptz | Yes | — | UTC | |
| location | geometry(Point,4326) | Yes | — | — | Grid point |
| value | numeric(8,4) | Yes | — | — | |
| created_at | timestamptz | Yes | now() | UTC | |

**Rules:**
- Large gridded datasets stored as NetCDF in MinIO. This table only stores scalar samples for querying.
- Unique `(source, variable, valid_time, location)`.

**Indexes:**
- `idx_env_source_var_time`
- `idx_env_location` GiST

---

### Table 12: jobs

**Purpose:** Durable job queue (mirrored in Redis for speed).

| Column | Type | Required | Default | Constraint | Description |
|---|---|---|---|---|---|
| id | UUID | Yes | gen_random_uuid() | PK | |
| job_type | text | Yes | — | — | 'drift_simulation', 'detection', 'attribution' |
| status | job_status_enum | Yes | 'queued' | — | |
| payload | jsonb | Yes | — | — | Parameters |
| idempotency_key | text | Yes | — | unique | Prevents dupes |
| started_at | timestamptz | No | null | UTC | |
| completed_at | timestamptz | No | null | UTC | |
| error_message | text | No | null | — | |
| retry_count | int | Yes | 0 | >= 0 | |
| created_at | timestamptz | Yes | now() | UTC | |

**Indexes:**
- `idx_jobs_status`
- `idx_jobs_idempotency` unique
- `idx_jobs_type`

---

## 6. Data Types and Enumerations

| Enum | Values | Transitions |
|---|---|---|
| vessel_type_enum | crude_tanker, chemical_tanker, cargo, container, fishing, tanker_other, unknown | Any → any |
| scene_status_enum | pending, pending_metadata, processing, processed, failed | pending → processing → processed/failed |
| spill_status_enum | detected, under_review, confirmed, rejected | detected → under_review → confirmed/rejected |
| drift_status_enum | queued, running, completed, failed | queued → running → completed/failed |
| dossier_status_enum | draft, finalized, superseded | draft → finalized → superseded |
| verdict_enum | prosecutable, person_of_interest, insufficient_evidence | Immutable |
| actor_type_enum | user, system, ai_agent | Immutable |
| audit_action_enum | create, update, delete, read, login, export, verdict_change | Immutable |
| job_status_enum | queued, running, completed, failed | queued → running → completed/failed |

**Invalid transitions:**
- Finalized dossier → draft (forbidden)
- Completed drift_run → queued (forbidden)

---

## 7. Complete SQL Schema

```sql
-- V001__enable_extensions.sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

```sql
-- V002__create_enums.sql
CREATE TYPE vessel_type_enum AS ENUM (
    'crude_tanker', 'chemical_tanker', 'cargo', 'container',
    'fishing', 'tanker_other', 'unknown'
);
CREATE TYPE scene_status_enum AS ENUM (
    'pending', 'pending_metadata', 'processing', 'processed', 'failed'
);
CREATE TYPE spill_status_enum AS ENUM (
    'detected', 'under_review', 'confirmed', 'rejected'
);
CREATE TYPE drift_status_enum AS ENUM (
    'queued', 'running', 'completed', 'failed'
);
CREATE TYPE dossier_status_enum AS ENUM (
    'draft', 'finalized', 'superseded'
);
CREATE TYPE verdict_enum AS ENUM (
    'prosecutable', 'person_of_interest', 'insufficient_evidence'
);
CREATE TYPE actor_type_enum AS ENUM ('user', 'system', 'ai_agent');
CREATE TYPE audit_action_enum AS ENUM (
    'create', 'update', 'delete', 'read', 'login', 'export', 'verdict_change'
);
CREATE TYPE job_status_enum AS ENUM (
    'queued', 'running', 'completed', 'failed'
);
```

```sql
-- V003__create_core_tables.sql (excerpt)
CREATE TABLE vessels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mmsi TEXT,
    imo TEXT,
    vessel_name TEXT NOT NULL,
    vessel_type vessel_type_enum NOT NULL DEFAULT 'unknown',
    flag_country_code CHAR(2),
    deadweight_tonnage NUMERIC(12,2) CHECK (deadweight_tonnage > 0),
    source TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_vessels_mmsi_format CHECK (mmsi IS NULL OR mmsi ~ '^[0-9]{9}$'),
    CONSTRAINT chk_vessels_imo_format CHECK (imo IS NULL OR imo ~ '^[0-9]{7}$')
);
CREATE UNIQUE INDEX uq_vessels_mmsi ON vessels(mmsi) WHERE mmsi IS NOT NULL;
CREATE UNIQUE INDEX uq_vessels_imo ON vessels(imo) WHERE imo IS NOT NULL;

CREATE TABLE tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vessel_id UUID NOT NULL REFERENCES vessels(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL,
    position GEOMETRY(Point, 4326) NOT NULL,
    speed_knots NUMERIC(5,2) NOT NULL CHECK (speed_knots >= 0 AND speed_knots <= 100),
    course_degrees NUMERIC(5,2) NOT NULL CHECK (course_degrees >= 0 AND course_degrees <= 360),
    heading_degrees NUMERIC(5,2) CHECK (heading_degrees >= 0 AND heading_degrees <= 360),
    navigational_status TEXT,
    source TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    ingestion_batch_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_tracks_source UNIQUE (source, source_record_id)
);
SELECT create_hypertable('tracks', 'recorded_at', chunk_time_interval => INTERVAL '7 days');
```

(Full SQL for remaining 10 tables follows the same pattern.)

```sql
-- V004__create_spatial_indexes.sql
CREATE INDEX idx_tracks_position ON tracks USING GIST (position);
CREATE INDEX idx_tracks_vessel_time ON tracks (vessel_id, recorded_at DESC);
CREATE INDEX idx_tracks_recorded_at_brin ON tracks USING BRIN (recorded_at);
CREATE INDEX idx_spills_polygon ON spills USING GIST (spill_polygon);
CREATE INDEX idx_scenes_footprint ON scenes USING GIST (footprint);
CREATE INDEX idx_ais_gaps_center ON ais_gaps USING GIST (gap_center);
CREATE INDEX idx_cpa_vessel_position ON cpa_events USING GIST (vessel_position_at_cpa);
CREATE INDEX idx_env_location ON environmental_data USING GIST (location);
```

```sql
-- V005__create_audit_protection.sql
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_no_update
BEFORE UPDATE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

CREATE TRIGGER trg_audit_no_delete
BEFORE DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

CREATE OR REPLACE FUNCTION prevent_finalized_dossier_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'finalized' THEN
        RAISE EXCEPTION 'Finalized dossiers are immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_dossier_immutable
BEFORE UPDATE ON dossiers
FOR EACH ROW EXECUTE FUNCTION prevent_finalized_dossier_change();
```

```sql
-- V006__updated_at_trigger.sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_vessels_updated_at BEFORE UPDATE ON vessels
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_scenes_updated_at BEFORE UPDATE ON scenes
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_spills_updated_at BEFORE UPDATE ON spills
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_drift_runs_updated_at BEFORE UPDATE ON drift_runs
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

```sql
-- V007__create_roles_and_grants.sql
CREATE ROLE app_runtime NOLOGIN;
CREATE ROLE migration NOLOGIN;
CREATE ROLE readonly NOLOGIN;
CREATE ROLE audit_writer NOLOGIN;

GRANT USAGE ON SCHEMA public TO app_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_runtime;
-- NO DELETE on audit_log
REVOKE DELETE ON audit_log FROM app_runtime;
REVOKE UPDATE ON audit_log FROM app_runtime;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
GRANT INSERT ON audit_log TO audit_writer;
```

---

## 8. Alembic Migration Plan

| Migration | Purpose | Rollback |
|---|---|---|
| V001__enable_extensions | PostGIS, pgcrypto, TimescaleDB | DROP EXTENSION (careful) |
| V002__create_enums | All enum types | DROP TYPE |
| V003__create_core_tables | 12 tables | DROP TABLE in reverse FK order |
| V004__create_spatial_indexes | GiST/BRIN indexes | DROP INDEX |
| V005__create_audit_protection | Triggers for immutability | DROP TRIGGER |
| V006__updated_at_trigger | Auto-update timestamps | DROP TRIGGER |
| V007__create_roles_and_grants | Roles | DROP ROLE (if no deps) |
| V008__seed_reference_data | Lookup data | DELETE FROM |

**Validation command:** `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`

---

## 9. Docker Compose Setup

```yaml
version: '3.8'
services:
  db:
    image: timescale/timescaledb-ha:pg16
    environment:
      POSTGRES_USER: payodi
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: payodi_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U payodi"]
      interval: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - miniodata:/data

volumes:
  pgdata:
  miniodata:
```

**.env.example:**
```
POSTGRES_PASSWORD=CHANGE_ME
MINIO_ROOT_USER=CHANGE_ME
MINIO_ROOT_PASSWORD=CHANGE_ME
DATABASE_URL=postgresql+asyncpg://payodi:CHANGE_ME@localhost:5432/payodi_db
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=CHANGE_ME
MINIO_SECRET_KEY=CHANGE_ME
```

**.gitignore:**
```
.env
__pycache__/
*.pyc
.venv/
node_modules/
dist/
```

**Commands:**
- Start: `docker compose up -d`
- Logs: `docker compose logs -f db`
- Connect: `docker exec -it <db-container> psql -U payodi -d payodi_db`
- Reset: `docker compose down -v && docker compose up -d`
- Migrations: `alembic upgrade head`

---

## 10. Backend Integration Contract (Python FastAPI)

- Use **Alembic**, not `Base.metadata.create_all()`, in production.
- Use **async SQLAlchemy 2.0** with `asyncpg` driver.
- Use transactions for multi-table workflows.
- Use optimistic locking (`version` column) on `vessels`, `scenes`, `spills`, `drift_runs`.
- Use **prepared statements** (SQLAlchemy does this automatically).
- Use **connection pooling** via SQLAlchemy engine.
- Use **keyset pagination** for tracks.
- Use **bulk inserts** (`session.bulk_insert_mappings`) for AIS.
- Validate with **Pydantic v2** before insert.
- Use **idempotency keys** for imports and jobs.
- Use **request_id** propagation for audit.


**JPA equivalent in Python:** Use SQLAlchemy ORM for CRUD. Use raw SQL (via `text()`) for:
- CPA/TCPA queries
- AIS gap detection
- Proximity searches
- Permutation tests

---

## 11. Critical Queries

1. **Create vessel:**
```sql
INSERT INTO vessels (mmsi, vessel_name, vessel_type, source)
VALUES ('123456789', 'MV Example', 'cargo', 'manual')
RETURNING id;
```

2. **Insert track:**
```sql
INSERT INTO tracks (vessel_id, recorded_at, position, speed_knots, course_degrees, source, source_record_id)
VALUES (
    $1, $2,
    ST_SetSRID(ST_MakePoint($3, $4), 4326),
    $5, $6, $7, $8
);
```

3. **Find vessels near spill:**
```sql
SELECT DISTINCT v.id, v.vessel_name
FROM vessels v
JOIN tracks t ON t.vessel_id = v.id
JOIN spills s ON s.id = $1
WHERE t.recorded_at BETWEEN $2 AND $3
  AND ST_DWithin(t.position::geography, s.spill_polygon::geography, 5000);
```

4. **Find AIS gaps:**
```sql
SELECT * FROM ais_gaps
WHERE vessel_id = $1
  AND gap_start BETWEEN $2 AND $3
  AND is_open_water = true;
```

5. **Create drift run:**
```sql
INSERT INTO drift_runs (scene_id, vessel_id, spill_id, simulation_version, model_parameters, run_fingerprint)
VALUES ($1, $2, $3, $4, $5, $6) RETURNING id;
```

6. **Save attribution scores:**
```sql
INSERT INTO attribution_scores (
    drift_run_id, scoring_version,
    cpa_score, dark_vessel_score, loitering_score,
    capacity_multiplier, draft_change_score,
    permutation_p_value, stability_index,
    total_score, verdict, explanation
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12);
```

7. **Finalize dossier:**
```sql
UPDATE dossiers
SET status = 'finalized', sha256 = $2
WHERE id = $1 AND status = 'draft';
```

8. **Audit history:**
```sql
SELECT * FROM audit_log
WHERE entity_type = $1 AND entity_id = $2
ORDER BY occurred_at DESC;
```

**Performance notes:**
- Query 3 uses GiST index on `tracks.position` and `spills.spill_polygon`.
- Query 4 uses BRIN index on `recorded_at` + B-tree on `vessel_id`.
- All queries use parameter binding (no string concat).

---

## 12. Validation Rules

- Required fields enforced at DB via NOT NULL.
- UTC enforced via timestamptz and application.
- Geometry: `ST_IsValid` on insert. `ST_MakeValid` before insert.
- Coordinate order: PostGIS uses `(longitude, latitude)` in `ST_MakePoint(lon, lat)`.
- Score ranges: 0–1 for pillar scores, 0–100 for total.
- Hash format: 64-char lowercase hex.
- Storage URI: no `user:pass@` in URI.
- Status transitions: enforced by trigger (see V005).
- FK existence: enforced by REFERENCES.
- Duplicate prevention: unique indexes.
- JSONB: schema validated by Pydantic on insert.
- Human review: `reviewed_by` required if `status = 'confirmed'`.
- Immutability: triggers prevent audit/dossier mutation.
- File/hash verification: recompute SHA-256 on read, compare.

---

## 13. AI Coding-Agent Instructions

**Rules for AI:**
- Read existing Alembic migrations before generating new schema changes.
- Never modify an already-applied migration. Add a new one.
- Never drop production data without approved migration + backup.
- Never use `SELECT *` in production code.
- Never concatenate user input into SQL.
- Never disable constraints to fix imports.
- Never store secrets in tables, logs, seed files, or code.
- Never silently swallow database exceptions.
- Never treat failed drift/scoring runs as deleted.
- Never update finalized dossiers.
- Never update or delete `audit_log`.
- Never fabricate schema fields not in this guide.
- Run migrations on clean DB and populated DB.
- Add tests for every constraint, index-dependent query, migration.
- State assumptions before coding. List files to change.
- Report migrations run, tests run, known limitations.

**Definition of complete checklist:**
- [ ] All 12 tables exist with constraints
- [ ] TimescaleDB hypertable created
- [ ] All GiST/BRIN indexes created
- [ ] Alembic migrations run cleanly on fresh DB
- [ ] Rollback works
- [ ] Audit log rejects UPDATE/DELETE
- [ ] Finalized dossier rejects UPDATE
- [ ] Test workflow end-to-end passes
- [ ] No secrets committed
- [ ] Documentation reviewed

---

## 14. Red Flags and Common Failure Modes

| Red Flag | Why Dangerous | Prevention | Detection | Recovery |
|---|---|---|---|---|
| Lat/long swapped | Wrong location, silent failures | Enforce PostGIS `ST_MakePoint(lon, lat)` | Compare to known landmarks | Re-import with correct order |
| Missing SRID | Spatial queries fail | Always `ST_SetSRID(..., 4326)` | `ST_SRID` check | Fix via UPDATE |
| Invalid polygons | PostGIS rejects | `ST_MakeValid` before insert | `ST_IsValid` check | Auto-fix, log warning |
| Float for scores | Precision loss | Use NUMERIC | Schema review | Migrate to NUMERIC |
| Duplicate AIS | Bloated tracks | Unique `(source, source_record_id)` | Count query | Delete dupes, re-import |
| Naive timestamps | Timezone bugs | timestamptz only | Schema scan | Convert all to UTC |
| Missing indexes | Slow queries | Add GiST/BRIN | `EXPLAIN ANALYZE` | Add index |
| JSONB overuse | No schema, slow | Only for extra fields | Schema review | Refactor to columns |
| Overwritten evidence | Legal loss | Triggers + audit | Audit log scan | Restore from backup |
| Mutable audit | Not court-valid | Trigger + role revoke | Permission test | Restore, re-lock |
| Hash only files | Metadata not proven | Hash snapshots too | Verify both | Re-hash |
| Hard-deletes | Evidence loss | Soft-delete flags | FK checks | Restore |
| Committed secrets | Security breach | `.gitignore` `.env` | `git log -p` | Rotate secrets |
| BLOBs in DB | DB bloat | Object storage | Size check | Migrate to MinIO |
| ORM schema in prod | Schema drift | Alembic only | `alembic current` | Reconcile |
| Long AIS transactions | Lock contention | Batch commits | `pg_stat_activity` | Split |
| No idempotency | Duplicate jobs | Fingerprint column | Compare runs | Delete dupes |
| No backup test | Silent data loss | Weekly restore drill | Cron log | Fix process |
| Public Postgres | Attack surface | Docker internal net | Port scan | Firewall |
| AI output uncriticized | Bugs, wrong schema | Human review | Diff against guide | Regenerate |

---

## 15. Edge Cases

| Case | Expected Behavior | DB Rule | Backend | Audit | Test |
|---|---|---|---|---|---|
| Vessel has MMSI, no IMO | Accept, imo null | Partial unique index | Allow | Create event | ✓ |
| Vessel name change | Update row, keep ID | No unique on name | Update + audit | Update event | ✓ |
| Two similar names | Both exist | No constraint | Disambiguate by MMSI | — | ✓ |
| AIS out of order | Sort by `recorded_at` before insert | — | Sort buffer | — | ✓ |
| Same AIS point twice | Reject second | Unique constraint | Catch IntegrityError | Warn | ✓ |
| Lat/lon = 0,0 | Reject | CHECK on position | Raise | Log | ✓ |
| Cross date line | PostGIS handles | No special rule | — | — | ✓ |
| Scene no wind | Null wind fields | Nullable | Use default | Note | ✓ |
| Multiple spills in scene | Multiple rows | — | Loop per spill | Create each | ✓ |
| Spill overlaps land | Reject or flag | `ST_Contains` land check | Human review | Create + flag | ✓ |
| Spill rejected by human | status = 'rejected' | Enum | Preserve geometry | Update event | ✓ |
| Drift fails midway | status = 'failed', error_message set | Preserve row | Retry as new run | Create event | ✓ |
| Retry with new params | New row, new fingerprint | Unique fingerprint | New job | Create event | ✓ |
| Scoring formula changes | New scoring_version | Unique (run, version) | New row | Create event | ✓ |
| Dossier correction | New dossier, supersedes link | Trigger blocks old | Insert new | Create event | ✓ |
| Source file moved | Update storage_uri | Nullable URI ok | Update | Update event | ✓ |
| Source hash changes | Flag as tampered | — | Reject | Alert | ✓ |
| User retries request | Idempotency key blocks dup | Unique key | Return cached | No double event | ✓ |
| Two workers same job | Second gets lock error | Row lock | Retry with backoff | Log | ✓ |
| Migration fails midway | Alembic stops, DB consistent | Transactional DDL | Rollback | Log | ✓ |
| Redis down | Fallback to Postgres jobs table | — | Degrade gracefully | Log | ✓ |
| DB down | API returns 503 | — | Retry | Alert | ✓ |
| Audit write fails | Block transaction | FK/trigger | Rollback | Alert | ✓ |
| Unauthorized access | 403 | RLS policy | Reject | Log attempt | ✓ |
| Secrets in metadata | Reject on insert | Pydantic validator | Strip | Log | ✓ |

---

## 16. Test Strategy

| Feature | Test Case | Expected | Priority | Automation |
|---|---|---|---|---|
| Migration | Fresh DB upgrade | All tables exist | Critical | CI |
| Migration | Rollback | Clean revert | Critical | CI |
| Constraint | Insert bad MMSI | Rejected | Critical | CI |
| Constraint | Insert dup track | Rejected | Critical | CI |
| Spatial | Find vessels near spill | Correct list | Critical | CI |
| Immutability | Update audit_log | Exception | Critical | CI |
| Immutability | Update finalized dossier | Exception | Critical | CI |
| Idempotency | Import same batch twice | No dupes | High | CI |
| Concurrency | Two workers same job | One fails | High | CI |
| Failure | Drift fails | Row preserved | High | CI |
| Performance | Bulk insert 100k tracks | < 10s | High | Manual |
| Backup | Restore drill | Data intact | High | Weekly |
| Security | App role DELETE audit | Denied | Critical | CI |
| Geospatial | MultiPolygon spill | Correct area | High | CI |
| Date line | Track crosses 180° | No error | Medium | CI |

Use **Testcontainers** with `timescale/timescaledb-ha:pg16` image.

---

## 17. Observability and Operations

**Health checks:**
- `pg_isready` for DB
- `redis-cli ping` for Redis
- MinIO `/minio/health/live`

**Metrics:**
- DB connections, slow queries, cache hit ratio, index usage
- Disk usage, WAL size, replication lag (if any)
- Redis memory, evictions
- Job queue depth, failure rate

**Backups:**
- Daily full backup (pg_dump)
- WAL archiving for point-in-time recovery
- Weekly restore drill to separate environment

**Retention:**
- tracks: 90 days hot, archive to MinIO cold
- audit_log: forever
- dossiers: forever
- drift_runs: forever
- spills, scenes: forever

**Incident response:**
- Corrupted geometry → validate, restore from backup, re-import
- Bad import → rollback batch by `ingestion_batch_id`
- Leaked credential → rotate, audit access log
- Failed migration → rollback via Alembic, investigate
- Suspicious audit activity → freeze writes, investigate chain

---

## 18. Step-by-Step Build Order

| # | Step | Command | Expected | Verify | Error | Fix |
|---|---|---|---|---|---|---|
| 1 | Install Docker | `docker --version` | Version shown | Version | Not installed | Install Docker Desktop |
| 2 | Create folders | `mkdir payodi && cd payodi` | Empty dir | `ls` | — | — |
| 3 | Create `.env` | Copy `.env.example` | File exists | `cat .env` | — | — |
| 4 | Start stack | `docker compose up -d` | 3 containers up | `docker ps` | Port in use | Change port |
| 5 | Verify DB | `docker exec ... pg_isready` | accepting connections | Output | Starting | Wait 10s |
| 6 | Init Alembic | `alembic init alembic` | Folder created | `ls alembic` | — | — |
| 7 | Enable extensions | Migration V001 | Success | `\dx` | Permission | Use superuser |
| 8 | Create enums | Migration V002 | Success | `\dT` | — | — |
| 9 | Create tables | Migration V003 | 12 tables | `\dt` | FK error | Order FKs |
| 10 | Indexes | Migration V004 | Indexes exist | `\di` | — | — |
| 11 | Audit protection | Migration V005 | Triggers exist | `\df` | — | — |
| 12 | Seed data | Migration V008 | 1 vessel, 1 scene | SELECT | — | — |
| 13 | Validation query | `SELECT COUNT(*)` | Counts match | Output | — | — |
| 14 | Connect FastAPI | `uvicorn app.main:app` | Server up | `curl /health` | Import error | Fix imports |
| 15 | Testcontainers | `pytest` | Tests pass | Output | Docker not running | Start Docker |
| 16 | Load test | Bulk insert 100k tracks | < 10s | Time | Slow | Tune batch size |
| 17 | Backup test | `pg_dump` + restore | Data intact | Compare | — | — |
| 18 | Mark complete | Update README | Checkbox ticked | Review | — | — |

---

## 19. MVP Acceptance Checklist

- [ ] Docker containers start successfully
- [ ] Health checks pass for DB, Redis, MinIO
- [ ] All 12 tables exist
- [ ] PostGIS enabled
- [ ] TimescaleDB hypertable created for tracks
- [ ] Alembic migrations run on fresh DB
- [ ] Alembic rollback works
- [ ] All constraints tested
- [ ] Test workflow (vessel → track → scene → spill → drift → score → dossier) passes
- [ ] Geospatial proximity query works
- [ ] Duplicate track import blocked or idempotent
- [ ] Failed simulation preserved and auditable
- [ ] Finalized dossier cannot be modified
- [ ] Audit record cannot be updated/deleted by app role
- [ ] Backup and restore test completed
- [ ] No secrets committed
- [ ] Documentation reviewed by human

---

## 20. First Developer Task

**Verify Docker installation and version.**

```bash
docker --version
docker compose version
```

If both commands work, proceed to Docker Compose setup.

If either command fails, install Docker Desktop first.