"""Point d'entrée de l'application FastAPI backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.analyses import router as analyses_router
from app.routes.datasets import router as datasets_router
from app.routes.exports import router as exports_router
from app.routes.health import router as health_router

app = FastAPI(
    title="A/B Analysis Workspace API",
    description="API REST pour la validation, le diagnostic et l'analyse fréquentiste de tests A/B.",
    version="0.1.0",
)

# CORS permissif pour le développement local et le conteneur Docker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montage des routes avec préfixe API v1
app.include_router(health_router, prefix="/api/v1", tags=["Health"])
app.include_router(datasets_router, prefix="/api/v1", tags=["Datasets"])
app.include_router(analyses_router, prefix="/api/v1", tags=["Analyses"])
app.include_router(exports_router, prefix="/api/v1", tags=["Exports"])


@app.get("/")
def root():
    return {"message": "A/B Analysis Workspace API", "docs": "/docs"}
