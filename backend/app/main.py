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

from app.routers.health import router as health_router
from app.routers.spills import router as spills_router
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
    title="Payodi Maritime Oil Spill Detection & Attribution API",
    description="Backend API integrating Phase 2 False-Positive Filtering with PostgreSQL/TimescaleDB",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(spills_router)


@app.get("/")
async def root():
    return {
        "service": "Payodi Oil Spill Detection & Vessel Attribution System",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_url": "/health",
    }
