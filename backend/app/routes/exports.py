"""Routes d'export de résultats (PDF, JSON, CSV)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Response

from app.schemas import AnalysisResponse, DataCsvExportRequest, PdfExportRequest
from app.services.export_service import (
    generate_data_csv,
    generate_pdf_report,
    generate_result_csv,
)

router = APIRouter()


@router.post("/exports/pdf")
def export_pdf(request: PdfExportRequest) -> Response:
    """Génère et télécharge le rapport PDF complet de l'analyse A/B."""
    try:
        pdf_bytes = generate_pdf_report(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur de génération PDF : {exc}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="rapport_ab_test.pdf"'},
    )


@router.post("/exports/json")
def export_json(request: AnalysisResponse) -> Response:
    """Génère et télécharge l'export JSON brut du résultat et de l'interprétation."""
    content = json.dumps(request.model_dump(), indent=2, ensure_ascii=False)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="resultat_ab_test.json"'},
    )


@router.post("/exports/csv")
def export_result_csv(request: AnalysisResponse) -> Response:
    """Télécharge le résultat aplati (une ligne par analyse) au format CSV."""
    return Response(
        content=generate_result_csv(request),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="resultat_ab_test.csv"'},
    )


@router.post("/exports/csv/data")
def export_data_csv(request: DataCsvExportRequest) -> Response:
    """Télécharge les observations analysées (après exclusions) au format CSV."""
    return Response(
        content=generate_data_csv(request),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="donnees_analysees.csv"'},
    )
