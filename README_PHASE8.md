# Phase 8 — Coast Guard Alert + Interception Fleet Availability

> **TL;DR** — When Phase 6 confirms an oil spill, Phase 8 finds the nearest
> Coast Guard station, counts interception assets nearby, and dispatches an
> SMS with an ETA. Live dashboard via WebSocket. Full architecture in
> [`PHASE8.md`](./PHASE8.md).

---

## What it does

1. **Listens** for a confirmed spill (via `dispatch_response` or the test endpoint)
2. **Selects** the nearest Coast Guard station (haversine, top 3 returned, closest is primary)
3. **Counts** interception-capable vessels within 100 km (merges Phase 4 output with a static fallback registry)
4. **Estimates** ETA from station distance ÷ 18-knot cruise speed
5. **Persists** the alert to SQLite (for history + acknowledgement)
6. **Broadcasts** over WebSocket to any connected dashboard
7. **Dispatches** an SMS to the primary station's duty officer

Three gates run before dispatch:
- `is_verified_oil == True`
- `filter_confidence >= 0.75`
- Not within a 30-minute cooldown for the same station

Anything that fails a gate is **suppressed** — logged server-side, not broadcast.

---

## Quick start

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
- Panel lights up with "Coast Guard Station Chennai"
- 2 interception assets, ETA ~0.4h, HIGH severity
- SMS status shows `skipped (dry_run)` — this is the default, safe mode
- Backend terminal also prints the SMS body. That's the message the duty officer would receive in live mode.

---

## SMS mode — dry-run vs live

Controlled by environment variables in `.env` (project root, gitignored — copy `.env.example` first):

```dotenv
PHASE8_DRY_RUN=true        # default — log SMS, no network call
SMS_PROVIDER=smsgatewayhub # or fast2sms
SMSGATEWAYHUB_API_KEY=     # required only when PHASE8_DRY_RUN=false
```

| `PHASE8_DRY_RUN` | API Key | Behavior |
|---|---|---|
| `true` | (any) | Logs SMS body, returns `skipped / dry_run`. No network call. |
| `false` | set | Live dispatch. Returns `sent` or `error`. |
| `false` | unset | Fail-safe: logs warning, returns `skipped / no_api_key`. |

Dry-run short-circuits before the network call even if a key is present. That means you can configure the key and still rehearse safely — flip `PHASE8_DRY_RUN=false` only on stage.

### Cost note
- **Quick SMS / Sandbox route**: No DLT registration required; useful for instant development testing.
- **DLT route**: ₹0.25 or less per SMS; requires one-time DLT entity + template registration for enterprise production.
- For the demo, dry-run mode is sufficient and free.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| WS | `/ws/responses` | Live alert stream |
| GET | `/api/responses` | Alert history (newest first) |
| POST | `/api/responses/{id}/ack` | Acknowledge an alert |
| POST | `/api/responses/test` | Fire a test alert |
| GET | `/api/stations` | List the 15-station registry |
| POST | `/api/interception-nearby` | Vessels near a coordinate |

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Test trigger from the terminal
```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/responses/test `
  -H "Content-Type: application/json" `
  -d '{"incident_id": "ENNORE_DEMO", "lat": 13.23, "lon": 80.33, "confidence": 0.96}'
```
*(PowerShell: use `curl.exe`, not `curl` — the built-in alias mangles JSON.)*

---

## The four-field contract

Phase 8 consumes this and nothing else. No coupling to Phase 4 internals — swap synthetic for real AIS and Phase 8 doesn't change.

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

## File map

```text
backend/notification/          Phase 8 engine
├── geo_utils.py               haversine, nearest-stations, vessel-proximity
├── sms_client.py              SMS dispatcher (SMSGatewayHub / Fast2SMS, dry-run capable)
├── response_engine.py         dispatch_response orchestrator
├── event_bus.py               asyncio pub/sub for WS fan-out
└── alerts.db                  SQLite (gitignored, auto-created)

backend/api/
├── main.py                    FastAPI app + CORS
└── response_api.py            REST + WebSocket router

data/response/
├── coast_guard_stations.json  15 ICG stations
└── interception_vessels.json  12 fallback ICG vessels

frontend/dashboard/
├── src/types/index.ts         CoastGuardAlert type
├── src/hooks/useResponses.ts  WS + REST hook
├── src/components/CoastGuardAlertPanel.tsx
├── src/App.tsx                demo triggers + history
└── vite.config.ts             /api + /ws proxies
```

---

## Demo flow

1. **Setup**: Backend + frontend running. Dashboard on the main screen. Backend terminal visible.
2. **Narration**: *"Phase 8 subscribes to Phase 6 confirmations. It selects the nearest Coast Guard command centre and counts interception assets within 100 km."*
3. **Trigger**: Click **Ennore / Chennai**.
4. **Display**: Panel lights up. Point out:
   - Coast Guard Station Chennai · 14.8 km · ETA 0.4h
   - 2 interception assets (ICGS Varuna, ICGS Vikram)
   - HIGH severity · 96.0% confidence
5. **SMS verification**: Switch to backend terminal to show the generated SMS block.
6. **Acknowledge**: Click **Acknowledge**. Panel flips to *Acked by duty.officer@icg*.
7. **Reset**: If a trigger says *"Suppressed: cooldown"*, reset via:
   ```powershell
   Remove-Item backend\notification\alerts.db
   ```

---

## Troubleshooting

- **`uvicorn: not recognized`**:
  Use `python -m uvicorn ...` instead.
- **`ModuleNotFoundError: No module named 'backend'`**:
  Run from the project root (folder containing `backend/`).
- **Dashboard shows `WS OFFLINE`**:
  - Backend must be running on `:8000`.
  - Vite must have the `/ws` proxy in `vite.config.ts`.
- **`curl : Cannot bind parameter 'Headers'`**:
  Use `curl.exe` instead of `curl` in PowerShell.
- **Trigger suppressed with `reason: "cooldown"`**:
  Expected behavior for duplicate triggers within 30 min. Reset `alerts.db` to bypass.
- **SMS returns `status: "error"`**:
  Check API key, credits, or phone number format.

---

## What Phase 8 does NOT do

- **No drift simulation** — Handled by Phase 3. Phase 8 consumes the origin.
- **No AIS correlation** — Handled by Phase 4. Phase 8 consumes the vessel list.
- **No ranking** — Handled by Phase 5. Phase 8 consumes the top suspect name.
- **No evidence generation** — Handled by Phase 6. Phase 8 consumes the confirmation.

Phase 8 is purely the operational response layer. Keeping it decoupled ensures it works smoothly with any Phase 4 implementation.

---

## Verification checklist

- [x] Backend starts cleanly (`/health` returns healthy)
- [x] `/docs` lists all REST endpoints
- [x] `/api/stations` returns 15 Coast Guard stations
- [x] `/api/interception-nearby` with Ennore coords returns 2 vessels
- [x] Dashboard runs on port 3000
- [x] Header shows `WS CONNECTED` green
- [x] Ennore trigger lights up the panel within 1s
- [x] Acknowledge button persists and broadcasts
- [x] Cooldown suppression functions on second trigger
- [x] `npx tsc --noEmit` passes with 0 errors
- [x] Git status clean
