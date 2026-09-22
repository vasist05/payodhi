"""API routers package."""
from app.routers.health import router as health_router
from app.routers.spills import router as spills_router

__all__ = ["health_router", "spills_router"]
