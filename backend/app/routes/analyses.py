"""Routes pour la sélection des méthodes et l'exécution des analyses statistiques."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
import numpy as np

from ab_stats import (
    Diagnostics,
    GroupMapping,
    MetricDeclaration,
    MetricType,
    NormalizedDataset,
    ValidationReport,
    diagnose,
    evaluate_compatibility,
)
from ab_stats.exceptions import ABStatsError
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    DiagnosticsRequest,
    MethodCompatibilitySchema,
    MethodsResponse,
    WarningSchema,
)
from app.services.analysis_service import run_analysis

router = APIRouter()


@router.post("/methods/compatibility", response_model=MethodsResponse)
def get_method_compatibility(request: DiagnosticsRequest) -> MethodsResponse:
    """Évalue la compatibilité, les hypothèses et les avertissements pour les 7 méthodes."""
    m_type = MetricType(request.metric_type)
    arr_a = np.asarray(request.group_a, dtype=float)
    arr_b = np.asarray(request.group_b, dtype=float)

    dummy_report = ValidationReport(
        n_input=arr_a.size + arr_b.size,
        n_retained=arr_a.size + arr_b.size,
        exclusions=(),
        group_mapping=GroupMapping("A", "B"),
        metric_declaration=MetricDeclaration(m_type, unit=request.unit if m_type is MetricType.CONTINUOUS else None),
        decimal_conversions=0,
        warnings=(),
        group_column_name="group",
        metric_column_name="metric",
    )
    dataset = NormalizedDataset(arr_a, arr_b, m_type, request.unit, dummy_report)

    try:
        diag = diagnose(dataset, confidence_level=request.confidence_level)
        comp_map = evaluate_compatibility(diag)
    except ABStatsError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict())

    methods_list = []
    for m, c in comp_map.items():
        methods_list.append(
            MethodCompatibilitySchema(
                method=c.method.value,
                compatible=c.compatible,
                reason=c.reason,
                assumptions=[
                    {
                        "code": a.code,
                        "description": a.description,
                        "status": a.status.value,
                        "detail": a.detail,
                    }
                    for a in c.assumptions
                ],
                warnings=[
                    WarningSchema(
                        code=w.code,
                        severity=w.severity.value,
                        message=w.message,
                        affected_field=w.affected_field,
                        suggested_alternative=w.suggested_alternative.value if w.suggested_alternative else None,
                    )
                    for w in c.warnings
                ],
                is_recommended=c.is_recommended,
            )
        )

    return MethodsResponse(methods=methods_list)


@router.post("/analyses", response_model=AnalysisResponse)
def execute_analysis(request: AnalysisRequest) -> AnalysisResponse:
    """Exécute une analyse statistique et génère son interprétation déterministe."""
    try:
        return run_analysis(request)
    except ABStatsError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
