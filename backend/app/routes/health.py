"""Route de vérification de l'état de l'API."""

from fastapi import APIRouter
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Retourne l'état opérationnel et la version de l'API."""
    return HealthResponse(status="ok", version="0.1.0")
