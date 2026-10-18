"""Routes FastAPI de l'application backend."""

from app.routes.analyses import router as analyses_router
from app.routes.datasets import router as datasets_router
from app.routes.exports import router as exports_router
from app.routes.health import router as health_router

__all__ = [
    "health_router",
    "datasets_router",
    "analyses_router",
    "exports_router",
]
