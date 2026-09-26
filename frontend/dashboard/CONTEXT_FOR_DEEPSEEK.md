# PAYODHI — Maritime Oil Spill Attribution System (SIH-26143)
> **Comprehensive Context & Developer Guide for DeepSeek / AI Pair-Programmers**
> *Prepared for instant context loading, vibe coding, refactoring, and feature expansion.*

---

## 1. Project Overview & Domain Context

**Project Name:** Payodhi (Front_pyodhi)  
**Organization / Domain:** Indian Coast Guard (ICG) & National Technical Research Organisation (NTRO)  
**Problem Statement:** Smart India Hackathon (SIH-26143) — Automated Satellite SAR Oil Spill Detection, Hydrodynamic Drift Hindcasting, and Multi-Factor Suspect Vessel Attribution.  
**Primary Goal:** Given satellite Synthetic Aperture Radar (SAR) imagery of an offshore oil slick, the system:
1. Detects and segments the dark slick polygon (SAR U-Net).
2. Filters out oceanic lookalikes (algal blooms, low wind shadows, biogenic films).
3. Simulates backward hydrodynamic drift (Lagrangian hindcasting using wind and current data from ERA5 & HYCOM) to calculate the spill origin coordinates and release time window.
4. Correlates Automatic Identification System (AIS) vessel traffic to find vessels that crossed the origin zone during the release window.
5. Scores and ranks candidate vessels using a 5-factor probabilistic attribution algorithm, flagging "dark vessels" (AIS transponder deliberately turned off or spoofed).
6. Generates an official, print-ready 8-section Maritime Intelligence Dossier for Coast Guard enforcement and prosecution.

---

## 2. Technology Stack & Key Libraries

| Category | Technology / Library | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Framework** | React + TypeScript | 18.3.1 / TS 5.7 | Single Page Application UI & state |
| **Build Tool** | Vite | 6.1.0 | Fast HMR dev server & production bundling |
| **Styling** | Tailwind CSS + PostCSS | 3.4.17 | Tactical dark mode theme, glassmorphism, responsive grid |
| **Mapping / GIS** | Leaflet + React-Leaflet | 1.9.4 / 4.2.1 | Interactive tactical map, polygons, drift vectors, tracks |
| **Visualizations**| Recharts | 3.10.1 | Radar charts (attribution factors), Area & Line charts |
| **Icons** | Lucide React | 0.475.0 | Comprehensive tactical, maritime, and UI icon set |
| **Utilities** | clsx, tailwind-merge | Latest | Conditional styling utilities |

### Dev Commands
```bash
npm install          # Install all dependencies
npm run dev          # Start local dev server (default port 3000 / 3001)
npm run build        # TypeScript compile (tsc) & Vite production build
npm run preview      # Preview production build locally
```

---

## 3. Directory & File Structure

Currently, the application logic is located primarily inside a single, rich file `src/App.tsx` (~2,310 lines), styled via `src/index.css` and configured via `tailwind.config.js`:

```text
Front_pyodhi-trail_front/
├── index.html               # Main entry HTML (JetBrains Mono & Inter fonts, Leaflet CSS)
├── package.json             # NPM dependencies and scripts
├── postcss.config.js        # PostCSS with Tailwind & Autoprefixer
├── tailwind.config.js       # Custom palette (tactical-dark, cyan, rose, amber, emerald)
├── tsconfig.json            # TypeScript compiler configuration (strict, ES2020)
├── tsconfig.node.json       # TypeScript node config
├── vite.config.ts           # Vite config with '@' alias pointing to './src'
├── src/
│   ├── App.tsx              # Core monolithic component (Types, Mock Data, UI, Sub-views)
│   ├── main.tsx             # React DOM root render
│   ├── index.css            # Tactical theme, glassmorphism, ticker & dossier print styles
│   └── vite-env.d.ts        # Vite client types
└── CONTEXT_FOR_DEEPSEEK.md  # THIS CONTEXT FILE
```

---

## 4. Architecture & Core Data Models

All primary TypeScript interfaces are defined at the top of `src/App.tsx`:

```typescript
export type LatLng = [number, number];

// Single GPS / AIS tracking point along a vessel's historical route
export interface TrackPoint {
  lat: number;
  lon: number;
  timestamp: string;      // ISO string
  sogKnots: number;       // Speed Over Ground in knots
  cogDegrees: number;     // Course Over Ground in degrees (0-360)
}

// Suspect vessel with forensic attribution scores and trajectory
export interface SuspectVessel {
  id: string;
  mmsi: string;           // Maritime Mobile Service Identity (or 'DARK-TGT-xxx')
  name: string;
  type: string;           // e.g. 'Petroleum Products Tanker', 'Crude Oil Tanker'
  flag: string;           // e.g. 'India (IN)', 'Liberia (LR)'
  lengthMeters: number;
  grossTonnage: number;
  lastCargo: string;      // e.g. 'Heavy Bunker Fuel', 'Arabian Light Crude'
  isDarkVessel: boolean;  // True if AIS was turned off / radar-only contact
  attributionScore: number; // 0 to 100 overall composite score
  evidenceGrade: 'STRONG' | 'INCONCLUSIVE' | 'LOW';
  
  // 5-Factor Weighted Sub-Scores (each 0 - 100):
  driftAgreement: number;        // Weight: 35% (Hydrodynamic physics match)
  timeOverlap: number;           // Weight: 25% (Co-location during release window)
  spatialProximity: number;      // Weight: 20% (Distance to calculated origin)
  vesselCharacteristics: number; // Weight: 10% (Cargo type, vessel size, ballast status)
  behavioralAnomaly: number;     // Weight: 10% (Course changes, speed drops, AIS gaps)
  
  distanceToOriginKm: number;    // Closest approach distance to origin centroid
  timeDiffMinutes: number;       // Delta between vessel transit and estimated release
  keyEvidence: string[];         // Bullet points supporting attribution
  disqualificationReasons: string[]; // Reasons why vessel might be ruled out
  track: TrackPoint[];           // Historical waypoint trajectory
}

// Origin probability distribution points from Lagrangian hindcast
export interface OriginHeatmapPoint {
  lat: number;
  lon: number;
  probability: number;    // 0.0 - 1.0
  radiusMeters: number;
}

// Trajectory steps for both backward hindcast and forward 24h drift forecast
export interface DriftTrajectoryPoint {
  hoursFromDetection: number; // Negative for hindcast (e.g. -7.5h), positive for forecast (e.g. +24h)
  lat: number;
  lon: number;
  timestamp: string;
  uncertaintyRadiusKm: number;
}

// Full incident dataset representing an active spill case
export interface IncidentCase {
  id: string;
  title: string;
  regionName: string;
  incidentDate: string;
  detectionTimestamp: string;
  estimatedReleaseWindow: {
    start: string;
    end: string;
    hoursBeforeDetection: number;
  };
  centerLat: number;
  centerLon: number;
  zoomLevel: number;
  slickPolygon: LatLng[];
  slickAreaKm2: number;
  slickPerimeterKm: number;
  estimatedVolumeBarrels: number;
  estimatedAgeHours: number;
  fpFilterConfidence: number;      // 0.0 - 1.0 (CNN confidence that slick is true mineral oil)
  isVerifiedOil: boolean;
  lookalikeCategoryChecked: string; // e.g. 'Algal Bloom & Coastal Wave Shadow'
  
  // Meteorological & Oceanographic Telemetry:
  windU10: number;                 // U-component 10m wind (m/s)
  windV10: number;                 // V-component 10m wind (m/s)
  windSpeedKnots: number;
  windDirectionDeg: number;
  oceanCurrentSpeedKnots: number;
  oceanCurrentDirDeg: number;
  seaSurfaceTempC: number;
  waveHeightM: number;
  
  backwardDriftPath: DriftTrajectoryPoint[];
  forwardDriftForecast: DriftTrajectoryPoint[];
  originHeatmap: OriginHeatmapPoint[];
  suspects: SuspectVessel[];
  summaryNotes: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
}
```

---

## 5. UI Views & Tab Architecture

The application has a unified top navigation bar and 7 primary tab views (`TabKey = 'dashboard' | 'map' | 'attribution' | 'ai' | 'analytics' | 'reports' | 'ingest'`):

### 1. Dashboard Tab (`activeTab === 'dashboard'`)
* **Live Tactical Mini-Map:** Embedded 460px interactive Leaflet map with direct link to Full Map.
* **Quick Ingest Dropzone:** Drag-and-drop satellite SAR image upload with preset sector selection.
* **Validation Case Card:** Quick summary of active case primary suspect, score, grade, and evidence.
* **Top KPIs:** Slick extent (km² & bbls), top attribution score, vessels tracked (including dark vessel counter), detection age.
* **Environmental Telemetry:** Live wind speed/dir, current speed/dir, significant wave height, sea surface temperature.
* **Pipeline Status:** Visual status indicators for the 6 pipeline phases (Pass/Fail).
* **Dark Vessel Alerts:** Warning ticker showing vessels with AIS OFF or suspicious behavioral anomalies with animated CRT scanlines.

### 2. Map View Tab (`activeTab === 'map'`)
* **Hero Tactical Map (`HeroMap`):** Fullscreen Leaflet map with 3 basemaps:
  - Satellite (ArcGIS World Imagery)
  - Dark Mode (ArcGIS World Dark Gray Base + Reference)
  - OpenStreetMap (Standard OSM)
* **GIS Overlays:**
  - `spillPolygon`: Red dashed polygon showing detected oil slick extent.
  - `originHeatmap`: Purple concentric circles indicating probabilistic origin spill zone.
  - `backwardDrift`: Purple dashed line tracing Lagrangian backward drift hindcast.
  - `forwardForecast`: Cyan dotted line with expanding uncertainty circles for T+6h, T+12h, T+24h.
  - `aisTracks`: Blue (normal), Amber (dark vessel), or Red (top suspect) vessel paths.
  - `pipelines`: Yellow dashed lines representing offshore submarine oil & gas pipelines.
* **Interactive Time Machine Scrub Bar (`TimeMachineStrip`):**
  - Scrub backwards from T-0 (detection) to T-X hours (estimated release time).
  - Play/Pause automated playback with smooth interpolation of vessel positions along historical tracks.
* **Layer Controls (`LayerControls`):** Floating bottom-left panel toggling each GIS layer visibility.
* **Tactical Status Bar (`StatusBar`):** Displays real-time cursor/center coordinates (Lat, Lon, Zoom).

### 3. Attribution Hub Tab (`activeTab === 'attribution'`)
* Detailed breakdown of the primary suspect and all ranked candidates.
* **5-Factor Radar Chart (`Recharts Radar`):**
  - Drift Physics Agreement (35%)
  - Temporal Window Overlap (25%)
  - Spatial Proximity (20%)
  - Vessel Characteristics & Cargo (10%)
  - Behavioral Anomaly & AIS gaps (10%)
* Key forensic evidence points, disqualification reasons, vessel dimensions, MMSI, and flag.

### 4. AI Maritime Console Tab (`activeTab === 'ai'`)
* Interactive chat interface ("Payodhi Copilot" / Maritime Forensic Assistant).
* Answers operational queries about slick dimensions, primary suspects, hydrodynamic drift physics, and MARPOL violation procedures.
* Dataset telemetry counter (AIS records processed, SAR passes, drift vectors).
* Pipeline health monitoring checklist.

### 5. Analytics Tab (`activeTab === 'analytics'`)
* **Spill Area Growth Chart:** Recharts AreaChart showing predicted dispersion and spreading kinetics.
* **Wind & Ocean Current Trends:** Recharts LineChart of 12-hour ERA5 wind and HYCOM current variations.
* **Meteorological Telemetry Grid:** U10/V10 vectors, wave height, SST, current direction, perimeter.

### 6. Intelligence Dossier / Reports Tab (`activeTab === 'reports'`)
* Formal, print-ready 8-section legal/military classified dossier branded for **Indian Coast Guard** & **NTRO**.
* Styled in off-white paper texture with navy blue accents (`#1e3a8a`), official letterhead, and "CLASSIFIED" watermark.
* Multi-page safe print styling (`@media print` in `index.css`) that formats cleanly into A4 PDF export.
* **Sections:**
  1. Executive Summary & Forensic Finding
  2. Incident Profile & Metadata
  3. Environmental Reanalysis (ERA5 + HYCOM)
  4. Six-Phase Forensic Pipeline Execution Audit
  5. Ranked Candidate Vessels Table
  6. Primary Suspect Detailed Evidentiary Chain & 5-Factor Score Matrix
  7. Operational Recommendations & Immediate Interception Directives
  8. Certification & Official Sign-off Lines

### 7. Ingest Scene Tab (`activeTab === 'ingest'`)
* Drag-and-drop SAR GeoTIFF/PNG/JPG image uploader with image preview.
* Preset Maritime Sectors:
  - Ennore / Kamarajar Port, Chennai (Bay of Bengal)
  - Visakhapatnam Outer Anchorage (Bay of Bengal)
  - Paradip Port, Odisha (Bay of Bengal)
  - Mumbai High Offshore Field (Arabian Sea)
  - Cochin Outer Roadstead (Arabian Sea)
* Wind Speed & Direction slider controls.
* Animated execution of all 6 Forensic Phases (`SAR Segmentation` → `FP Filtering` → `Drift Hindcast` → `AIS Correlation` → `Attribution` → `Dossier`) resulting in synthetic incident generation and seamless injection into app state.

---

## 6. Built-in Preset Incidents & Scenarios

The codebase comes with two realistic, pre-configured validation cases:

1. **`chennai-2017` (Primary Incident):**
   - **Title:** *Chennai / Ennore Tanker Collision*
   - **Date:** 2017-01-28 | Coordinates: 13.255°N, 80.365°E
   - **Slick Area:** 34.2 km² (~1,850 barrels Heavy Bunker Fuel)
   - **Primary Suspect:** *MT Dawn Kanchipuram* (Score: 96/100, Grade: STRONG)
   - **Secondary Vessel:** *BW Maple* (Score: 68/100, Grade: INCONCLUSIVE — LPG carrier, non-persistent cargo)
   - **Dark Target:** *Unidentified Radar Target* (Score: 62/100 — SAR return with no AIS)

2. **`mumbai-2023`:**
   - **Title:** *Mumbai High Offshore Incident*
   - **Date:** 2023-11-05 | Coordinates: 19.380°N, 71.420°E
   - **Slick Area:** 24.8 km² (~620 barrels Arabian Light Crude)
   - **Primary Suspect:** *MT Gulf Trader* (Score: 84/100, Grade: STRONG)

---

## 7. Styling & Design System Rules

* **Design Aesthetic:** High-tech tactical command room / defense intelligence console.
* **Palette:**
  - Base background: `#050810` (Ultra-dark navy)
  - Card/Panel backgrounds: `#0a0f1a` / `#0f172a` with blur (`backdrop-blur-md`, `backdrop-blur-xl`)
  - Borders: `rgba(6, 182, 212, 0.18)` (Electric cyan translucent)
  - Primary accents: Cyan (`#06b6d4`), Navy (`#1e3a8a`), Emerald (`#10b981`), Amber (`#f59e0b`), Rose (`#f43f5e`)
* **Typography:**
  - UI Text: `Inter`, system-ui
  - Telemetry & Data: `JetBrains Mono`, monospace
  - Dossier / Legal Report: `Georgia`, serif headings with monospace tables
* **Custom CSS Classes (in `src/index.css`):**
  - `.glass-panel`: standard tactical frosted container
  - `.glass-panel-strong`: high-contrast modal frosted container
  - `.glass-card`: hoverable translucent cards
  - `.pulsing-slick`: pulse animation for emergency slicks
  - `.animate-scanline`: CRT radar scanline animation
  - `.dossier-page`: light printable paper canvas for reports

---

## 8. Ideal Vibe Coding Roadmap & Future Work

When prompting DeepSeek or building further features, consider these high-impact tasks:

### Phase A: Modularization & Clean Refactoring
Break down the 2,310-line `src/App.tsx` into clean, maintainable modules:
- `src/types/incident.ts`: Type definitions (`IncidentCase`, `SuspectVessel`, etc.)
- `src/data/mockIncidents.ts`: `INCIDENT_CASES` and `PRESET_SECTORS`
- `src/components/common/`: `Navbar`, `TabBar`, `LiveEventTicker`, `UTCClock`, `StatusBar`
- `src/components/map/`: `HeroMap`, `LayerControls`, `TimeMachineStrip`
- `src/components/dashboard/`: `DashboardIngestPanel`, `DashboardValidationCase`, `DashKPI`
- `src/components/attribution/`: `AttributionFullPage`, `AttributionFloatingPanel`
- `src/components/reports/`: `ReportsInline`, `ReportSection`, `InfoCell`
- `src/components/ingest/`: `IngestInline`
- `src/components/ai/`: `AIConsoleInline`
- `src/components/analytics/`: `AnalyticsInline`

### Phase B: Real Backend API Integration
Connect the frontend to a real backend (e.g. FastAPI / Python):
- `POST /api/sar/upload`: Upload real Sentinel-1 GeoTIFF / PNG images.
- `POST /api/pipeline/run`: Trigger actual Python ML models (SAR U-Net segmentation, CNN lookalike classifier).
- `GET /api/drift/hindcast`: Fetch Eulerian-Lagrangian drift vectors computed via OpenDrift / NOAA GNOME.
- `GET /api/ais/intersect`: Query live AIS databases (AISHub, Spire, or MarineTraffic) within the computed space-time origin envelope.
- `GET /api/reports/pdf`: Generate native PDF downloads using WeasyPrint or Puppeteer.

### Phase C: Advanced UI Enhancements
- **Multi-Incident Comparison:** Compare two spill cases side-by-side.
- **Dynamic Oil Weathering Model:** Display Fay's spreading algorithm and evaporation curve over time.
- **Custom Vessel Search:** Allow searching vessels by IMO, MMSI, or callsign.
- **Sound Effects & Haptics:** Tactical audio beeps on new target detection or critical alert triggers.
- **Map Ruler / Measure Tool:** Measure distance from slick boundary to coastline or EEZ limits.

---

## 9. Prompt Template for DeepSeek

When starting a conversation with DeepSeek, you can paste the following prompt:

> *"I am working on the **Payodhi** frontend (Maritime Oil Spill Detection & Attribution System for SIH-26143 / NTRO). It is a React 18 + TypeScript + Vite + Tailwind CSS + Leaflet application. I have loaded the full architectural context from `CONTEXT_FOR_DEEPSEEK.md`. I want to [insert your task, e.g. refactor App.tsx into separate modular component files / add an interactive measurement tool on the Leaflet map / connect the AI console to an Ollama or OpenAI endpoint / add real PDF export]. Please maintain the tactical dark aesthetic and preserve all existing data structures."*
