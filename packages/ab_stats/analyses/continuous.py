"""Analyses statistiques pour métriques continues paramétriques (tests de Student et de Welch).

Deux méthodes au catalogue :
* ``welch_t`` : test t de Welch pour variances inégales (le choix par défaut recommandé).
* ``student_t`` : test t classique de Student supposant des variances égales.
"""

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
from ab_stats.confidence_intervals import (
    student_mean_ci,
    welch_mean_ci,
)
from ab_stats.data import NormalizedDataset
from ab_stats.effect_sizes import build_cohens_d, build_hedges_g
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
    "welch_t",
    "student_t",
]


def _extract_continuous_arrays(
    group_a: Any,
    group_b: Any,
) -> tuple[np.ndarray, np.ndarray, str, int]:
    """Extrait deux tableaux NumPy 1D continus, l'unité et le nombre de lignes exclues."""
    if isinstance(group_a, NormalizedDataset):
        return group_a.group_a, group_a.group_b, group_a.unit, group_a.report.n_excluded

    arr_a = np.asarray(group_a, dtype=float)
    arr_b = np.asarray(group_b, dtype=float)

    if arr_a.ndim != 1 or arr_b.ndim != 1:
        raise InvalidParameterError(
            "INVALID_SAMPLE_DIMENSION",
            "Les échantillons doivent être unidimensionnels.",
        )
    if arr_a.size < 2 or arr_b.size < 2:
        raise InvalidParameterError(
            "INSUFFICIENT_SAMPLE_SIZE",
            "Chaque groupe doit contenir au moins 2 observations pour estimer la variance.",
            details={"n_a": int(arr_a.size), "n_b": int(arr_b.size)},
        )
    if not (np.all(np.isfinite(arr_a)) and np.all(np.isfinite(arr_b))):
        raise InvalidParameterError(
            "NON_FINITE_DATA",
            "Les échantillons ne doivent contenir aucune valeur infinie ou NaN.",
        )

    return arr_a, arr_b, "unit", 0


def _continuous_diagnostics(
    arr_a: np.ndarray,
    arr_b: np.ndarray,
    equal_var: bool,
) -> tuple[tuple[Assumption, ...], tuple[AnalysisWarning, ...]]:
    """Génère les hypothèses et avertissements diagnostiques pour les tests t."""
    n_a, n_b = arr_a.size, arr_b.size
    min_n = min(n_a, n_b)
    max_n = max(n_a, n_b)
    balance_ratio = max_n / min_n if min_n > 0 else float("inf")

    # Skewness
    skew_a = float(stats.skew(arr_a, bias=False)) if n_a >= 3 else 0.0
    skew_b = float(stats.skew(arr_b, bias=False)) if n_b >= 3 else 0.0
    high_skew = abs(skew_a) > 1.0 or abs(skew_b) > 1.0

    # Outliers par méthode Tukey
    def count_outliers(arr: np.ndarray) -> int:
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        if iqr == 0:
            return 0
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return int(np.sum((arr < lower) | (arr > upper)))

    outliers_a = count_outliers(arr_a)
    outliers_b = count_outliers(arr_b)
    has_outliers = (outliers_a > 0) or (outliers_b > 0)

    # Ratio de variance
    var_a = float(np.var(arr_a, ddof=1))
    var_b = float(np.var(arr_b, ddof=1))
    max_var = max(var_a, var_b)
    min_var = min(var_a, var_b)
    var_ratio = max_var / min_var if min_var > 0 else float("inf")

    warnings: list[AnalysisWarning] = []
    assumptions_list: list[Assumption] = [
        Assumption(
            code="INDEPENDENCE",
            description="Observations indépendantes au sein de et entre les groupes.",
            status=AssumptionStatus.UNVERIFIABLE,
            detail="Dépend de la randomisation du test A/B.",
        ),
        Assumption(
            code="NORMALITY_OF_MEANS",
            description="Normalité approximative des moyennes d'échantillons (TCL si n >= 30).",
            status=AssumptionStatus.SATISFIED if min_n >= 30 else AssumptionStatus.UNVERIFIABLE,
            detail=f"Effectifs observés : n_A={n_a}, n_B={n_b}.",
        ),
    ]

    if equal_var:
        equal_var_status = (
            AssumptionStatus.VIOLATED if var_ratio > 2.0 else AssumptionStatus.SATISFIED
        )
        assumptions_list.append(
            Assumption(
                code="HOMOSCEDASTICITY",
                description="Égalité des variances des deux groupes (homoscédasticité).",
                status=equal_var_status,
                detail=f"Rapport des variances max/min : {var_ratio:.2f}.",
            )
        )
        if var_ratio > 2.0:
            warnings.append(
                AnalysisWarning(
                    code="UNEQUAL_VARIANCES",
                    severity=Severity.WARNING,
                    message=(
                        f"Les variances des groupes sont très inégales (rapport de {var_ratio:.2f} > 2.0). "
                        "Le test t de Welch est recommandé car il ne suppose pas l'égalité des variances."
                    ),
                    suggested_alternative=Method.WELCH_T,
                )
            )

    if min_n < 30:
        warnings.append(
            AnalysisWarning(
                code="SMALL_SAMPLE",
                severity=Severity.WARNING,
                message=f"Au moins un groupe a un effectif faible ({min_n} < 30). Le test t est sensible aux non-normalités.",
            )
        )

    if high_skew:
        warnings.append(
            AnalysisWarning(
                code="HIGH_SKEWNESS",
                severity=Severity.WARNING,
                message="Forte asymétrie observée dans au moins un groupe (|skewness| > 1.0).",
                suggested_alternative=Method.MANN_WHITNEY_U,
            )
        )

    if has_outliers:
        warnings.append(
            AnalysisWarning(
                code="OUTLIERS_DETECTED",
                severity=Severity.WARNING,
                message="Des valeurs aberrantes ont été détectées au-delà de 1,5 x IQR.",
                suggested_alternative=Method.MANN_WHITNEY_U,
            )
        )

    if balance_ratio >= 4.0:
        warnings.append(
            AnalysisWarning(
                code="UNBALANCED_GROUPS",
                severity=Severity.INFO,
                message=f"Déséquilibre important des effectifs (ratio {balance_ratio:.1f} >= 4.0).",
            )
        )

    return tuple(assumptions_list), tuple(warnings)


def welch_t(
    group_a: Any,
    group_b: Any,
    *,
    alpha: float = 0.05,
    alternative: Alternative | str = Alternative.TWO_SIDED,
    confidence_level: float | None = None,
    unit: str = "unit",
    seed: int | None = None,
) -> StatisticalResult:
    """Test t de Welch pour deux échantillons indépendants à variances inégales (B - A)."""
    validate_alpha(alpha)
    alt = normalize_alternative(alternative)
    conf_level = 1.0 - alpha if confidence_level is None else confidence_level
    validate_confidence_level(conf_level)

    arr_a, arr_b, inferred_unit, n_excluded = _extract_continuous_arrays(group_a, group_b)
    final_unit = inferred_unit if inferred_unit != "unit" else unit

    n_a = int(arr_a.size)
    n_b = int(arr_b.size)
    mean_a = float(np.mean(arr_a))
    mean_b = float(np.mean(arr_b))
    sd_a = float(np.std(arr_a, ddof=1))
    sd_b = float(np.std(arr_b, ddof=1))
    diff = mean_b - mean_a

    if sd_a == 0.0 and sd_b == 0.0:
        raise DegenerateSampleError(
            "ZERO_VARIANCE",
            "La variance des deux groupes est nulle ; le test t est indéfini.",
        )

    scipy_alt = to_scipy_alternative(alt)
    # SciPy ttest_ind compare le premier argument au second : on passe B en premier pour tester B - A
    res = stats.ttest_ind(arr_b, arr_a, equal_var=False, alternative=scipy_alt)
    t_stat = float(res.statistic)
    p_val = float(res.pvalue)
    df = float(res.df) if hasattr(res, "df") else float(n_a + n_b - 2)

    ci = welch_mean_ci(mean_a, sd_a, n_a, mean_b, sd_b, n_b, confidence_level=conf_level)
    effect = (
        build_hedges_g(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
        if min(n_a, n_b) < 30
        else build_cohens_d(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
    )
    rel_lift = (mean_b - mean_a) / abs(mean_a) if mean_a != 0 else None

    assumptions, warnings = _continuous_diagnostics(arr_a, arr_b, equal_var=False)
    decision = Decision.REJECT_NULL if p_val <= alpha else Decision.FAIL_TO_REJECT_NULL

    null_text = "La moyenne du groupe B est égale à la moyenne du groupe A."
    if alt is Alternative.GREATER:
        alt_text = "La moyenne du groupe B est supérieure à celle du groupe A."
    elif alt is Alternative.LESS:
        alt_text = "La moyenne du groupe B est inférieure à celle du groupe A."
    else:
        alt_text = "Les moyennes des groupes A et B sont différentes."

    return StatisticalResult(
        method=Method.WELCH_T,
        metric_type=MetricType.CONTINUOUS,
        hypotheses=Hypotheses(
            alternative=alt,
            null_text=null_text,
            alternative_text=alt_text,
        ),
        groups=Groups(
            a=GroupSummary(n=n_a, mean=mean_a, sd=sd_a, median=float(np.median(arr_a))),
            b=GroupSummary(n=n_b, mean=mean_b, sd=sd_b, median=float(np.median(arr_b))),
        ),
        statistic=Statistic(name="t", value=t_stat, df=df),
        alpha=alpha,
        decision=decision,
        estimate=Estimate(
            name=EstimateName.DIFFERENCE_OF_MEANS,
            value=float(diff),
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
        warnings=warnings,
    )


def student_t(
    group_a: Any,
    group_b: Any,
    *,
    alpha: float = 0.05,
    alternative: Alternative | str = Alternative.TWO_SIDED,
    confidence_level: float | None = None,
    unit: str = "unit",
    seed: int | None = None,
) -> StatisticalResult:
    """Test t classique de Student pour deux échantillons indépendants (B - A)."""
    validate_alpha(alpha)
    alt = normalize_alternative(alternative)
    conf_level = 1.0 - alpha if confidence_level is None else confidence_level
    validate_confidence_level(conf_level)

    arr_a, arr_b, inferred_unit, n_excluded = _extract_continuous_arrays(group_a, group_b)
    final_unit = inferred_unit if inferred_unit != "unit" else unit

    n_a = int(arr_a.size)
    n_b = int(arr_b.size)
    mean_a = float(np.mean(arr_a))
    mean_b = float(np.mean(arr_b))
    sd_a = float(np.std(arr_a, ddof=1))
    sd_b = float(np.std(arr_b, ddof=1))
    diff = mean_b - mean_a

    if sd_a == 0.0 and sd_b == 0.0:
        raise DegenerateSampleError(
            "ZERO_VARIANCE",
            "La variance des deux groupes est nulle ; le test t est indéfini.",
        )

    scipy_alt = to_scipy_alternative(alt)
    res = stats.ttest_ind(arr_b, arr_a, equal_var=True, alternative=scipy_alt)
    t_stat = float(res.statistic)
    p_val = float(res.pvalue)
    df = float(n_a + n_b - 2)

    ci = student_mean_ci(mean_a, sd_a, n_a, mean_b, sd_b, n_b, confidence_level=conf_level)
    effect = (
        build_hedges_g(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
        if min(n_a, n_b) < 30
        else build_cohens_d(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
    )
    rel_lift = (mean_b - mean_a) / abs(mean_a) if mean_a != 0 else None

    assumptions, warnings = _continuous_diagnostics(arr_a, arr_b, equal_var=True)
    decision = Decision.REJECT_NULL if p_val <= alpha else Decision.FAIL_TO_REJECT_NULL

    null_text = "La moyenne du groupe B est égale à la moyenne du groupe A."
    if alt is Alternative.GREATER:
        alt_text = "La moyenne du groupe B est supérieure à celle du groupe A."
    elif alt is Alternative.LESS:
        alt_text = "La moyenne du groupe B est inférieure à celle du groupe A."
    else:
        alt_text = "Les moyennes des groupes A et B sont différentes."

    return StatisticalResult(
        method=Method.STUDENT_T,
        metric_type=MetricType.CONTINUOUS,
        hypotheses=Hypotheses(
            alternative=alt,
            null_text=null_text,
            alternative_text=alt_text,
        ),
        groups=Groups(
            a=GroupSummary(n=n_a, mean=mean_a, sd=sd_a, median=float(np.median(arr_a))),
            b=GroupSummary(n=n_b, mean=mean_b, sd=sd_b, median=float(np.median(arr_b))),
        ),
        statistic=Statistic(name="t", value=t_stat, df=df),
        alpha=alpha,
        decision=decision,
        estimate=Estimate(
            name=EstimateName.DIFFERENCE_OF_MEANS,
            value=float(diff),
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
        warnings=warnings,
    )
