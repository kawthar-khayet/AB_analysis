"""Analyses statistiques par rééchantillonnage (tests de permutation et bootstrap)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from ab_stats.analyses._common import (
    build_reproducibility,
    normalize_alternative,
    validate_alpha,
    validate_confidence_level,
    validate_n_resamples,
    validate_seed,
)
from ab_stats.confidence_intervals import percentile_bootstrap_ci
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
    Statistic,
    StatisticalResult,
)

__all__ = [
    "permutation_test",
    "bootstrap_test",
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


def permutation_test(
    group_a: Any,
    group_b: Any,
    *,
    alpha: float = 0.05,
    alternative: Alternative | str = Alternative.TWO_SIDED,
    confidence_level: float | None = None,
    n_resamples: int = 10_000,
    seed: int = 42,
    unit: str = "unit",
) -> StatisticalResult:
    """Test de permutation de Monte-Carlo sur la différence des moyennes (B - A).

    L'intervalle de confiance associé est calculé par bootstrap percentile avec la même graine,
    déclaré comme tel dans le contrat.
    """
    validate_alpha(alpha)
    alt = normalize_alternative(alternative)
    conf_level = 1.0 - alpha if confidence_level is None else confidence_level
    validate_confidence_level(conf_level)
    validate_n_resamples(n_resamples)
    validate_seed(seed)

    arr_a, arr_b, inferred_unit, n_excluded = _extract_arrays(group_a, group_b)
    final_unit = inferred_unit if inferred_unit != "unit" else unit

    n_a = int(arr_a.size)
    n_b = int(arr_b.size)
    mean_a = float(np.mean(arr_a))
    mean_b = float(np.mean(arr_b))
    diff_obs = mean_b - mean_a

    combined = np.concatenate([arr_a, arr_b])
    rng = np.random.default_rng(seed)

    perm_diffs = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        shuffled = rng.permutation(combined)
        perm_diffs[i] = np.mean(shuffled[n_a:]) - np.mean(shuffled[:n_a])

    # Calcul de la p-value empirique exacte
    if alt is Alternative.GREATER:
        p_val = float((1 + np.sum(perm_diffs >= diff_obs)) / (n_resamples + 1))
    elif alt is Alternative.LESS:
        p_val = float((1 + np.sum(perm_diffs <= diff_obs)) / (n_resamples + 1))
    else:
        p_val = float((1 + np.sum(np.abs(perm_diffs) >= abs(diff_obs))) / (n_resamples + 1))

    # Bootstrap compagnon pour l'IC percentile
    boot_diffs = np.empty(n_resamples, dtype=float)
    boot_rng = np.random.default_rng(seed)
    for i in range(n_resamples):
        sample_a = boot_rng.choice(arr_a, size=n_a, replace=True)
        sample_b = boot_rng.choice(arr_b, size=n_b, replace=True)
        boot_diffs[i] = np.mean(sample_b) - np.mean(sample_a)

    ci = percentile_bootstrap_ci(boot_diffs, confidence_level=conf_level)

    sd_a = float(np.std(arr_a, ddof=1)) if n_a > 1 else 0.0
    sd_b = float(np.std(arr_b, ddof=1)) if n_b > 1 else 0.0
    effect = (
        build_hedges_g(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
        if min(n_a, n_b) < 30
        else build_cohens_d(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
    )
    rel_lift = (mean_b - mean_a) / abs(mean_a) if mean_a != 0 else None

    assumptions = (
        Assumption(
            code="EXCHANGEABILITY",
            description="Sous H0, les observations proviennent de la même distribution et sont échangeables.",
            status=AssumptionStatus.SATISFIED,
        ),
        Assumption(
            code="INDEPENDENCE",
            description="Les tirages sont mutuellement indépendants.",
            status=AssumptionStatus.UNVERIFIABLE,
        ),
    )

    decision = Decision.REJECT_NULL if p_val <= alpha else Decision.FAIL_TO_REJECT_NULL

    null_text = "Les distributions de A et B sont identiques sous H0."
    if alt is Alternative.GREATER:
        alt_text = "La moyenne de B est supérieure à celle de A."
    elif alt is Alternative.LESS:
        alt_text = "La moyenne de B est inférieure à celle de A."
    else:
        alt_text = "La moyenne de B est différente de celle de A."

    return StatisticalResult(
        method=Method.PERMUTATION,
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
        statistic=Statistic(name="mean_diff", value=float(diff_obs)),
        alpha=alpha,
        decision=decision,
        estimate=Estimate(
            name=EstimateName.DIFFERENCE_OF_MEANS,
            value=float(diff_obs),
            unit=final_unit,
        ),
        confidence_interval=ci,
        effect_size=effect,
        reproducibility=build_reproducibility(arr_a, arr_b, seed=seed, n_resamples=n_resamples),
        p_value=p_val,
        p_value_source=PValueSource.PERMUTATION,
        relative_lift=rel_lift,
        n_excluded=n_excluded,
        assumptions=assumptions,
        warnings=(),
    )


def bootstrap_test(
    group_a: Any,
    group_b: Any,
    *,
    alpha: float = 0.05,
    alternative: Alternative | str = Alternative.TWO_SIDED,
    confidence_level: float | None = None,
    n_resamples: int = 10_000,
    seed: int = 42,
    unit: str = "unit",
) -> StatisticalResult:
    """Test bootstrap de la différence des moyennes (B - A) avec p-value shifted."""
    validate_alpha(alpha)
    alt = normalize_alternative(alternative)
    conf_level = 1.0 - alpha if confidence_level is None else confidence_level
    validate_confidence_level(conf_level)
    validate_n_resamples(n_resamples)
    validate_seed(seed)

    arr_a, arr_b, inferred_unit, n_excluded = _extract_arrays(group_a, group_b)
    final_unit = inferred_unit if inferred_unit != "unit" else unit

    n_a = int(arr_a.size)
    n_b = int(arr_b.size)
    mean_a = float(np.mean(arr_a))
    mean_b = float(np.mean(arr_b))
    diff_obs = mean_b - mean_a

    rng = np.random.default_rng(seed)

    boot_diffs = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        s_a = rng.choice(arr_a, size=n_a, replace=True)
        s_b = rng.choice(arr_b, size=n_b, replace=True)
        boot_diffs[i] = np.mean(s_b) - np.mean(s_a)

    ci = percentile_bootstrap_ci(boot_diffs, confidence_level=conf_level)

    # P-value bootstrap sous H0 en décalant les échantillons vers la moyenne globale
    pooled_mean = float(np.mean(np.concatenate([arr_a, arr_b])))
    shifted_a = arr_a - mean_a + pooled_mean
    shifted_b = arr_b - mean_b + pooled_mean

    h0_rng = np.random.default_rng(seed + 1)
    h0_diffs = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        s_a = h0_rng.choice(shifted_a, size=n_a, replace=True)
        s_b = h0_rng.choice(shifted_b, size=n_b, replace=True)
        h0_diffs[i] = np.mean(s_b) - np.mean(s_a)

    if alt is Alternative.GREATER:
        p_val = float((1 + np.sum(h0_diffs >= diff_obs)) / (n_resamples + 1))
    elif alt is Alternative.LESS:
        p_val = float((1 + np.sum(h0_diffs <= diff_obs)) / (n_resamples + 1))
    else:
        p_val = float((1 + np.sum(np.abs(h0_diffs) >= abs(diff_obs))) / (n_resamples + 1))

    sd_a = float(np.std(arr_a, ddof=1)) if n_a > 1 else 0.0
    sd_b = float(np.std(arr_b, ddof=1)) if n_b > 1 else 0.0
    effect = (
        build_hedges_g(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
        if min(n_a, n_b) < 30
        else build_cohens_d(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
    )
    rel_lift = (mean_b - mean_a) / abs(mean_a) if mean_a != 0 else None

    assumptions = (
        Assumption(
            code="REPRESENTATIVE_SAMPLE",
            description="L'échantillon empirique est représentatif de la population sous-jacente.",
            status=AssumptionStatus.SATISFIED if min(n_a, n_b) >= 30 else AssumptionStatus.UNVERIFIABLE,
            detail=f"Effectifs : n_A={n_a}, n_B={n_b}.",
        ),
        Assumption(
            code="INDEPENDENCE",
            description="Observations indépendantes et identiquement distribuées.",
            status=AssumptionStatus.UNVERIFIABLE,
        ),
    )

    decision = Decision.REJECT_NULL if p_val <= alpha else Decision.FAIL_TO_REJECT_NULL

    null_text = "La vraie différence de moyennes entre B et A est nulle."
    if alt is Alternative.GREATER:
        alt_text = "La moyenne de B est strictement supérieure à celle de A."
    elif alt is Alternative.LESS:
        alt_text = "La moyenne de B est strictement inférieure à celle de A."
    else:
        alt_text = "La différence de moyennes entre B et A est non nulle."

    return StatisticalResult(
        method=Method.BOOTSTRAP,
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
        statistic=Statistic(name="mean_diff", value=float(diff_obs)),
        alpha=alpha,
        decision=decision,
        estimate=Estimate(
            name=EstimateName.DIFFERENCE_OF_MEANS,
            value=float(diff_obs),
            unit=final_unit,
        ),
        confidence_interval=ci,
        effect_size=effect,
        reproducibility=build_reproducibility(arr_a, arr_b, seed=seed, n_resamples=n_resamples),
        p_value=p_val,
        p_value_source=PValueSource.BOOTSTRAP_SHIFTED,
        relative_lift=rel_lift,
        n_excluded=n_excluded,
        assumptions=assumptions,
        warnings=(),
    )
