"""Analyses statistiques non paramétriques (test de Mann-Whitney U et estimateur de Hodges-Lehmann)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats

from ab_stats.analyses._common import (
    build_reproducibility,
    normalize_alternative,
    to_scipy_alternative,
    validate_alpha,
    validate_confidence_level,
)
from ab_stats.confidence_intervals import hodges_lehmann_ci
from ab_stats.data import NormalizedDataset
from ab_stats.effect_sizes import build_cliffs_delta
from ab_stats.exceptions import DegenerateSampleError, InvalidParameterError
from ab_stats.results import (
    Alternative,
    AnalysisWarning,
    Assumption,
    AssumptionStatus,
    Decision,
    Estimate,
    EstimateName,
    GroupSummary,
    Groups,
    Hypotheses,
    Method,
    MetricType,
    PValueSource,
    Severity,
    Statistic,
    StatisticalResult,
)

__all__ = [
    "mann_whitney_u",
]


def _extract_arrays(group_a: Any, group_b: Any) -> tuple[np.ndarray, np.ndarray, str, int]:
    if isinstance(group_a, NormalizedDataset):
        return group_a.group_a, group_a.group_b, group_a.unit, group_a.report.n_excluded

    arr_a = np.asarray(group_a, dtype=float)
    arr_b = np.asarray(group_b, dtype=float)

    if arr_a.ndim != 1 or arr_b.ndim != 1:
        raise InvalidParameterError(
            "INVALID_SAMPLE_DIMENSION",
            "Les échantillons doivent être unidimensionnels.",
        )
    if arr_a.size == 0 or arr_b.size == 0:
        raise InvalidParameterError(
            "EMPTY_SAMPLE",
            "Les échantillons ne peuvent pas être vides.",
        )
    return arr_a, arr_b, "unit", 0


def mann_whitney_u(
    group_a: Any,
    group_b: Any,
    *,
    alpha: float = 0.05,
    alternative: Alternative | str = Alternative.TWO_SIDED,
    confidence_level: float | None = None,
    unit: str = "unit",
    seed: int | None = None,
) -> StatisticalResult:
    """Test non-paramétrique U de Mann-Whitney (orienté B versus A).

    L'estimé associé est le décalage de Hodges-Lehmann (médiane de toutes les différences B - A).
    La taille d'effet associée est le delta de Cliff.
    """
    validate_alpha(alpha)
    alt = normalize_alternative(alternative)
    conf_level = 1.0 - alpha if confidence_level is None else confidence_level
    validate_confidence_level(conf_level)

    arr_a, arr_b, inferred_unit, n_excluded = _extract_arrays(group_a, group_b)
    final_unit = inferred_unit if inferred_unit != "unit" else unit

    n_a = int(arr_a.size)
    n_b = int(arr_b.size)
    combined = np.concatenate([arr_a, arr_b])

    if np.unique(combined).size == 1:
        raise DegenerateSampleError(
            "CONSTANT_DATA",
            "Toutes les observations sont identiques ; le test U est dégénéré.",
        )

    scipy_alt = to_scipy_alternative(alt)
    # B en premier argument pour comparer B à A
    res = stats.mannwhitneyu(arr_b, arr_a, alternative=scipy_alt, method="auto")
    u_stat = float(res.statistic)
    p_val = float(res.pvalue)

    # Estimateur de Hodges-Lehmann : médiane des paires (b_j - a_i)
    pairwise_diffs = (arr_b[:, np.newaxis] - arr_a[np.newaxis, :]).ravel()
    hl_estimate = float(np.median(pairwise_diffs))

    ci = hodges_lehmann_ci(arr_a, arr_b, confidence_level=conf_level)
    effect = build_cliffs_delta(arr_a, arr_b)

    med_a = float(np.median(arr_a))
    med_b = float(np.median(arr_b))
    rel_lift = (med_b - med_a) / abs(med_a) if med_a != 0 else None

    ties_count = int(combined.size - np.unique(combined).size)
    warnings: list[AnalysisWarning] = []
    if ties_count > 0:
        warnings.append(
            AnalysisWarning(
                code="TIES_PRESENT",
                severity=Severity.INFO,
                message=f"Présence d'égalités ({ties_count} doublons). Les rangs moyens sont utilisés.",
            )
        )

    assumptions = (
        Assumption(
            code="INDEPENDENCE",
            description="Observations indépendantes au sein de et entre les groupes.",
            status=AssumptionStatus.UNVERIFIABLE,
        ),
        Assumption(
            code="ORDINAL_OR_CONTINUOUS",
            description="La métrique est au moins ordinale (permet de classer les valeurs).",
            status=AssumptionStatus.SATISFIED,
        ),
        Assumption(
            code="STOCHASTIC_DOMINANCE",
            description="Le test évalue la supériorité stochastique P(B > A) vs P(A > B), pas directement les médianes.",
            status=AssumptionStatus.SATISFIED,
        ),
    )

    decision = Decision.REJECT_NULL if p_val <= alpha else Decision.FAIL_TO_REJECT_NULL

    null_text = "La distribution de B ne domine pas stochastiquement celle de A (P(B > A) = P(A > B))."
    if alt is Alternative.GREATER:
        alt_text = "B tend à prendre des valeurs supérieures à celles de A."
    elif alt is Alternative.LESS:
        alt_text = "B tend à prendre des valeurs inférieures à celles de A."
    else:
        alt_text = "Les distributions de A et B diffèrent en rang."

    return StatisticalResult(
        method=Method.MANN_WHITNEY_U,
        metric_type=MetricType.CONTINUOUS,
        hypotheses=Hypotheses(
            alternative=alt,
            null_text=null_text,
            alternative_text=alt_text,
        ),
        groups=Groups(
            a=GroupSummary(
                n=n_a, mean=float(np.mean(arr_a)), sd=float(np.std(arr_a, ddof=1)) if n_a > 1 else None, median=med_a
            ),
            b=GroupSummary(
                n=n_b, mean=float(np.mean(arr_b)), sd=float(np.std(arr_b, ddof=1)) if n_b > 1 else None, median=med_b
            ),
        ),
        statistic=Statistic(name="U", value=u_stat),
        alpha=alpha,
        decision=decision,
        estimate=Estimate(
            name=EstimateName.HODGES_LEHMANN,
            value=hl_estimate,
            unit=final_unit,
        ),
        confidence_interval=ci,
        effect_size=effect,
        reproducibility=build_reproducibility(arr_a, arr_b, seed=seed),
        p_value=p_val,
        p_value_source=PValueSource.ANALYTIC,
        relative_lift=rel_lift,
        n_excluded=n_excluded,
        assumptions=assumptions,
        warnings=tuple(warnings),
    )
