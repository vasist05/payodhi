"""
backend/app/main.py

FastAPI main application entrypoint for Payodi.
Configures CORS, lifespan startup checks, and routes for spills and health.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.attribution import router as attribution_router
from app.routers.detection import router as detection_router
from app.routers.drift import router as drift_router
from app.routers.health import router as health_router
from app.routers.pipeline import router as pipeline_router
from app.routers.spills import router as spills_router
from backend.api.response_api import router as response_router
from app.services.storage import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("payodi.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Payodi API service...")
    try:
        storage.ensure_buckets()
        log.info("MinIO buckets verified.")
    except Exception as exc:
        log.warning("Could not initialize MinIO buckets at startup: %s", exc)
    yield
    log.info("Shutting down Payodi API service...")


app = FastAPI(
    title="Payodi Maritime Oil Spill Detection, Attribution & Response API",
    description="Unified API integrating Phase 1 (Detection), Phase 2 (Filter), Phase 3 (Drift), Phase 4 (AIS & Dark Vessels), Phase 5/6 (Forensic Attribution & Dossiers), and Phase 8 (Coast Guard Maritime Response)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(spills_router)
app.include_router(detection_router)
app.include_router(drift_router)
app.include_router(attribution_router, prefix="/api/v1/attribution", tags=["attribution"])
app.include_router(pipeline_router)
app.include_router(response_router)



@app.get("/")
async def root():
    return {
        "service": "Payodi Oil Spill Detection & Vessel Attribution System",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_url": "/health",
    }
