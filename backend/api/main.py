"""FastAPI application entry point.

Mounts the Phase 8 response router and configures CORS for the dev
dashboard. CORS uses explicit localhost origins because
allow_origins=["*"] combined with allow_credentials=True is invalid
per the Fetch spec and rejected by browsers.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.response_api import router as response_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Payodhi — Phase 8 Response API",
    version="0.1.0",
    description="Coast Guard alert + interception fleet availability.",
)

# ---- CORS ------------------------------------------------------------
# Explicit origins only — wildcard + credentials is invalid and
# breaks the WebSocket handshake from the dev dashboard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers ---------------------------------------------------------
app.include_router(response_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "phase8-response-api", "status": "ok"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}