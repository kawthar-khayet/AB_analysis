"""Service d'orchestration pour l'exécution des analyses statistiques."""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from ab_stats import (
    Alternative,
    AnalysisOutcome,
    Interpretation,
    Method,
    MetricType,
    StatisticalResult,
    bootstrap_test,
    fisher_exact,
    interpret,
    mann_whitney_u,
    permutation_test,
    student_t,
    two_proportion_z,
    welch_t,
)
from ab_stats.exceptions import InvalidParameterError
from app.schemas import AnalysisRequest, AnalysisResponse


def _to_json_compatible(obj: Any) -> Any:
    """Convertit récursivement les dataclasses et énumérations en dictionnaires sérialisables JSON."""
    if dataclasses.is_dataclass(obj):
        res = {}
        for f in dataclasses.fields(obj):
            val = getattr(obj, f.name)
            res[f.name] = _to_json_compatible(val)
        return res
    if isinstance(obj, (list, tuple)):
        return [_to_json_compatible(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_json_compatible(v) for k, v in obj.items()}
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if hasattr(obj, "isoformat"):  # Datetime
        return obj.isoformat()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    return obj


def run_analysis(request: AnalysisRequest) -> AnalysisResponse:
    """Exécute l'analyse statistique demandée et construit l'interprétation associée."""
    method_str = request.method
    try:
        method = Method(method_str)
    except ValueError:
        raise InvalidParameterError(
            "UNKNOWN_METHOD",
            f"Méthode statistique inconnue : {method_str}",
            details={"allowed": [m.value for m in Method]},
        )

    alt = Alternative(request.alternative)
    group_a = np.asarray(request.group_a, dtype=float)
    group_b = np.asarray(request.group_b, dtype=float)

    if method is Method.TWO_PROPORTION_Z:
        res = two_proportion_z(
            group_a,
            group_b,
            alpha=request.alpha,
            alternative=alt,
            confidence_level=request.confidence_level,
            seed=request.seed,
        )
    elif method is Method.FISHER_EXACT:
        res = fisher_exact(
            group_a,
            group_b,
            alpha=request.alpha,
            alternative=alt,
            confidence_level=request.confidence_level,
            seed=request.seed,
        )
    elif method is Method.WELCH_T:
        res = welch_t(
            group_a,
            group_b,
            alpha=request.alpha,
            alternative=alt,
            confidence_level=request.confidence_level,
            unit=request.unit,
            seed=request.seed,
        )
    elif method is Method.STUDENT_T:
        res = student_t(
            group_a,
            group_b,
            alpha=request.alpha,
            alternative=alt,
            confidence_level=request.confidence_level,
            unit=request.unit,
            seed=request.seed,
        )
    elif method is Method.MANN_WHITNEY_U:
        res = mann_whitney_u(
            group_a,
            group_b,
            alpha=request.alpha,
            alternative=alt,
            confidence_level=request.confidence_level,
            unit=request.unit,
            seed=request.seed,
        )
    elif method is Method.PERMUTATION:
        res = permutation_test(
            group_a,
            group_b,
            alpha=request.alpha,
            alternative=alt,
            confidence_level=request.confidence_level,
            n_resamples=request.n_resamples,
            seed=request.seed,
            unit=request.unit,
        )
    elif method is Method.BOOTSTRAP:
        res = bootstrap_test(
            group_a,
            group_b,
            alpha=request.alpha,
            alternative=alt,
            confidence_level=request.confidence_level,
            n_resamples=request.n_resamples,
            seed=request.seed,
            unit=request.unit,
        )
    else:
        raise InvalidParameterError("UNSUPPORTED_METHOD", f"Méthode non implémentée: {method}")

    # Interprétation déterministe
    interp = interpret(res, delta=request.delta)

    result_dict = _to_json_compatible(res)
    interp_dict = _to_json_compatible(interp) if interp is not None else None

    return AnalysisResponse(
        result=result_dict,
        interpretation=interp_dict,
    )
