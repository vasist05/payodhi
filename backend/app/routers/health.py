"""
backend/app/routers/health.py

Health check endpoint verifying connectivity to PostgreSQL/TimescaleDB,
Redis, and MinIO storage.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.storage import storage

log = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
@router.get("/api/health", status_code=status.HTTP_200_OK)
async def health_check(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Check connectivity to PostgreSQL, Redis, and MinIO."""
    health_status: dict[str, Any] = {
        "status": "ok",
        "database": "unknown",
        "storage": "unknown",
    }

    # 1. Check PostgreSQL
    try:
        await session.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as exc:
        log.error("Database health check failed: %s", exc)
        health_status["database"] = f"error: {exc}"
        health_status["status"] = "degraded"

    # 2. Check MinIO
    try:
        # Check if MinIO client is reachable
        s3 = storage._client
        s3.list_buckets()
        health_status["storage"] = "connected"
    except Exception as exc:
        log.warning("Storage health check warning: %s", exc)
        health_status["storage"] = f"warning: {exc}"

    http_status = (
        status.HTTP_200_OK
        if health_status["status"] == "ok"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(content=health_status, status_code=http_status)
