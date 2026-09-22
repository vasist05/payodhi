# Phase 8 — Coast Guard Alert + Interception Fleet Availability

> **TL;DR** — When Phase 6 confirms an oil spill, Phase 8 finds the nearest
> Coast Guard station, counts interception assets nearby, and dispatches an
> SMS with an ETA. Live dashboard via WebSocket. Full architecture in
> [`PHASE8.md`](./PHASE8.md).

---

## 🎯 What it does & How it Works

Phase 8 is the operational action layer of Payodhi. It translates satellite-derived oil spill detections and vessel tracking into an immediate response in **under 30 seconds**:

1. **Listens** for a confirmed spill (via `dispatch_response` or the REST demo endpoint).
2. **Evaluates 3 Safety Gates**:
   - `is_verified_oil == True` (suppresses unverified anomalies)
   - `filter_confidence >= 0.75` (ensures high detection certainty)
   - `30-minute cooldown` per station (prevents alert spamming during ongoing incidents)
3. **Selects** the nearest Coast Guard command centre using spherical Haversine distance (top 3 identified, closest is primary).
4. **Counts & Identifies** interception-capable patrol vessels within 100 km (merges live Phase 4 AIS positions with a static fallback registry).
5. **Estimates** response ETA based on primary station distance ÷ 18-knot interception cruising speed.
6. **Persists** the complete alert record into SQLite (`alerts.db`) for duty audit logs and acknowledgement.
7. **Broadcasts** the alert frame over an asynchronous `EventBus` to all connected WebSocket clients in real-time.
8. **Dispatches** an SMS alert to the duty officer's mobile phone via SMSGatewayHub or Fast2SMS.

---

## 📐 Architecture & Data Flow

```text
┌────────────────────────────────┐
│  Phase 6 / Pipeline Trigger    │  (Spill confirmed: lat, lon, confidence, suspect)
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  3 Verification & Safety Gates │
│  1. is_verified_oil == True    │  (Suppresses false alarms)
│  2. confidence >= 0.75         │  (Minimum certainty required)
│  3. 30-min station cooldown    │  (Prevents spamming the same station)
└───────────────┬────────────────┘
                │ Passed
                ▼
┌─────────────────────────────────────────────────────────────┐
│  Geo-Spatial Response Engine (response_engine.py)          │
│  • Great-circle Haversine distance to 15 Coast Guard bases  │
│  • Selects Primary station + Backup stations                │
│  • Counts interception assets (patrol boats) within 100 km  │
│  • Calculates ETA: Distance ÷ 18 knots cruise speed         │
└───────┬───────────────────────┬─────────────────────┬───────┘
        │                       │                     │
        ▼                       ▼                     ▼
┌───────────────┐       ┌───────────────┐     ┌───────────────┐
│ SQLite DB     │       │ Event Bus     │     │ SMS Client    │
│ (alerts.db)   │       │ (event_bus.py)│     │ (sms_client)  │
│ • Full record │       │ • Async Queue │     │ • Formats msg │
│ • Ack tracking│       │ • WS Fan-out  │     │ • SMSGateway  │
└───────────────┘       └───────┬───────┘     │   / Fast2SMS  │
                                │             └───────────────┘
                                ▼
                    ┌────────────────────────┐
                    │ React Tactical UI      │
                    │ • Instant WS render    │
                    │ • One-click Duty Ack   │
                    └────────────────────────┘
```

---

## 🚀 Quick start

**Prerequisites:** Python 3.10+, Node 18+. Two terminals.

### Terminal 1 — Backend
From the project root:
```powershell
python -m uvicorn backend.api.main:app --reload --port 8000
```
Wait for `Application startup complete`. Health check:
```powershell
curl http://127.0.0.1:8000/health
# {"status":"healthy"}
```

### Terminal 2 — Dashboard
```powershell
cd frontend\dashboard
npm install # first time only
npm run dev
```
Opens `http://localhost:3000` automatically. The header badge should show **`WS CONNECTED`** in green.

### Fire a test alert
In the dashboard, click **Ennore / Chennai**. Within one second:
- Panel lights up with **Coast Guard Station Chennai**
- 2 interception assets (`ICGS Varuna`, `ICGS Vikram`), ETA ~0.4h, `HIGH` severity
- SMS status shows `skipped (dry_run)` — this is the default safe mode
- Backend terminal prints the exact SMS message the duty officer receives.

---

## 📱 SMS Dispatch — Dry-Run vs Live Gateway

Controlled by environment variables in `.env` (project root, gitignored — copy `.env.example` first):

```dotenv
# Live toggle: true = simulated logging | false = real network dispatch
PHASE8_DRY_RUN=false

# Provider selection: 'smsgatewayhub' (default) or 'fast2sms'
SMS_PROVIDER=smsgatewayhub

# SMSGatewayHub Sandbox / Live API credentials
SMSGATEWAYHUB_API_KEY=your_key_here
SMSGATEWAYHUB_SENDER_ID=TESTIN

# Fast2SMS credentials (alternate provider)
FAST2SMS_API_KEY=

# Personal Mobile Override: redirects all test alerts to your personal number
ALERT_PHONE_OVERRIDE=9876543210
```

| `PHASE8_DRY_RUN` | API Key | Behavior |
|---|---|---|
| `true` | (any) | Logs SMS body to terminal, returns `skipped / dry_run`. No network call. |
| `false` | set | Live dispatch to phone number via selected provider. Returns `sent` or `error`. |
| `false` | unset | Fail-safe: logs warning, returns `skipped / no_api_key`. |

### Phone Number Sanitization & Overrides
- **`ALERT_PHONE_OVERRIDE`**: When set in `.env`, all alerts automatically divert to your test mobile number instead of the dummy station contact (`+91XXXXXXXXXX`).
- **Formatting**: Automatically cleans whitespace, hyphens, and formats 10-digit Indian numbers with the standard `91` country prefix.

---

## 🔌 Endpoints

| Method | Path | Purpose |
|---|---|---|
| WS | `/ws/responses` | Live streaming alert push |
| GET | `/api/responses` | Alert history from SQLite (newest first) |
| POST | `/api/responses/{id}/ack` | Duty officer alert acknowledgement |
| POST | `/api/responses/test` | Trigger a test alert through the dispatch pipeline |
| GET | `/api/stations` | List the full 15-station Coast Guard registry |
| POST | `/api/interception-nearby` | Query vessels within $N$ km of any coordinate |

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Test trigger from the terminal
```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/responses/test `
  -H "Content-Type: application/json" `
  -d '{"incident_id": "ENNORE_DEMO", "lat": 13.23, "lon": 80.33, "confidence": 0.96}'
```
*(PowerShell: use `curl.exe`, not `curl` — the built-in alias mangles JSON.)*

---

## 📄 The 4-Field Contract

Phase 8 consumes this contract and nothing else. No direct coupling to Phase 4 AIS internals — swapping synthetic data for real AIS feeds requires zero changes to Phase 8.

```python
incident = {
    "id": "ENNORE_2024_001",
    "lat": 13.23,
    "lon": 80.33,
    "is_verified_oil": True,         # Phase 2
    "filter_confidence": 0.96,       # Phase 2
    "detection_confidence": 0.94,    # Phase 2
    "top_suspect_name": "DAWN KANCHIPURAM", # Phase 5
}
vessels = [
    {
        "mmsi": "419000103",
        "name": "ICGS Varuna",
        "type": "Patrol Vessel",
        "lat": 13.12,
        "lon": 80.32,
    },
    # Accepts position_lat / position_lon as well — Phase 4 raw output works directly.
]
await dispatch_response(incident, vessels)
```

---

## 🗂️ File Map

```text
backend/notification/          Phase 8 Core Engine
├── geo_utils.py               Haversine calculation, nearest stations, vessel proximity
├── sms_client.py              SMSGatewayHub & Fast2SMS dispatcher + number sanitization
├── response_engine.py         dispatch_response orchestrator & gating
├── event_bus.py               Lightweight asyncio pub/sub queue for WS fan-out
└── alerts.db                  SQLite runtime persistence (gitignored, auto-created)

backend/api/                   FastAPI Service
├── main.py                    FastAPI app + explicit localhost CORS
└── response_api.py            REST endpoints + WebSocket /ws/responses router

data/response/                 Reference Registries
├── coast_guard_stations.json  15 Indian Coast Guard stations (coords, radii, phone, region)
└── interception_vessels.json  12 fallback ICG patrol vessels (MMSI, speed, home port)

frontend/dashboard/            Tactical Dashboard
├── src/types/index.ts         CoastGuardAlert & IncidentCase contracts
├── src/hooks/useResponses.ts  WebSocket connection with auto-reconnect + REST history hook
├── src/components/CoastGuardAlertPanel.tsx  Defensive dark tactical display card
├── src/App.tsx                Preset demo trigger bar + live alert viewer + history log
└── vite.config.ts             /api and /ws proxies to backend (:8000)
```

---

## 🎭 Demo Flow (Pitch Narrative)

1. **Setup**: Backend + Frontend running. Dashboard on screen, backend terminal visible.
2. **Narration**: *"Phase 8 subscribes to Phase 6 confirmations. It selects the nearest Coast Guard command centre and counts interception assets within 100 km."*
3. **Trigger**: Click **Ennore / Chennai** on the UI.
4. **Instant Display**: Panel renders immediately:
   - **Station**: Coast Guard Station Chennai (14.8 km away)
   - **ETA**: 0.4 hours (at 18 kn cruising speed)
   - **Assets in range**: 2 (`ICGS Varuna`, `ICGS Vikram`)
   - **Severity**: HIGH · 96.0% confidence
5. **SMS Verification**: Switch to backend terminal to show the generated SMS alert payload.
6. **Acknowledge**: Click **Acknowledge**. Panel updates to *Acked by duty.officer@icg* across all connected dashboards.
7. **Reset**: If a trigger is suppressed due to cooldown, clear `alerts.db`:
   ```powershell
   Remove-Item backend\notification\alerts.db
   ```

---

## 🛠️ Troubleshooting

- **`uvicorn: not recognized`**:
  Run `python -m uvicorn ...` instead.
- **`ModuleNotFoundError: No module named 'backend'`**:
  Execute commands from the project root directory.
- **Dashboard shows `WS OFFLINE`**:
  - Ensure backend is running on `http://127.0.0.1:8000`.
  - Vite must have the `/ws` proxy configured in `vite.config.ts`.
- **`curl : Cannot bind parameter 'Headers'`**:
  In PowerShell, run `curl.exe` instead of `curl`.
- **Trigger suppressed with `reason: "cooldown"`**:
  Expected behavior when triggering the same station within 30 minutes. Reset `alerts.db` to test again.

---

## 🚫 What Phase 8 does NOT do

- **No drift simulation** — Handled by Phase 3 (Phase 8 consumes the final origin).
- **No AIS correlation** — Handled by Phase 4 (Phase 8 consumes the vessel list).
- **No suspect ranking** — Handled by Phase 5 (Phase 8 consumes the top suspect name).
- **No evidence dossier generation** — Handled by Phase 6 (Phase 8 consumes the confirmation).

Phase 8 is strictly the operational dispatch layer, keeping it decoupled and resilient.

---

## ✅ Verification Checklist

- [x] Backend starts cleanly (`/health` returns healthy)
- [x] `/docs` lists all 5 REST & WS endpoints
- [x] `/api/stations` returns the 15-station registry
- [x] `/api/interception-nearby` returns nearest vessels
- [x] Dashboard runs on port 3000
- [x] Header shows `WS CONNECTED` green
- [x] Ennore trigger lights up the panel within 1s
- [x] Acknowledge button persists and broadcasts
- [x] Cooldown suppression functions on duplicate triggers
- [x] `npx tsc --noEmit` compiles with 0 errors
- [x] Git status clean
