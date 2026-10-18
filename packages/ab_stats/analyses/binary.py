"""Analyses statistiques pour métriques binaires (A/B testing).

Deux méthodes au catalogue :
* ``two_proportion_z`` : test z asymptotique pour la différence de deux proportions (B - A).
* ``fisher_exact`` : test exact de Fisher sur tableau de contingence 2x2.
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
    newcombe_proportion_ci,
    unpooled_proportion_ci,
)
from ab_stats.data import NormalizedDataset
from ab_stats.effect_sizes import build_cohens_h
from ab_stats.exceptions import DegenerateSampleError, InvalidParameterError
from ab_stats.results import (
    UNIT_PROPORTION,
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
    "two_proportion_z",
    "fisher_exact",
]


def _extract_binary_arrays(
    group_a: Any,
    group_b: Any,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Extrait deux tableaux NumPy 1D binaires et le nombre de lignes exclues."""
    if isinstance(group_a, NormalizedDataset):
        return group_a.group_a, group_a.group_b, group_a.report.n_excluded

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
            details={"n_a": int(arr_a.size), "n_b": int(arr_b.size)},
        )
    # Vérification binaire {0, 1}
    unique_a = set(np.unique(arr_a))
    unique_b = set(np.unique(arr_b))
    if not (unique_a.issubset({0.0, 1.0}) and unique_b.issubset({0.0, 1.0})):
        raise InvalidParameterError(
            "NON_BINARY_DATA",
            "Les valeurs d'une métrique binaire doivent être 0 ou 1.",
        )

    return arr_a, arr_b, 0


def two_proportion_z(
    group_a: Any,
    group_b: Any,
    *,
    alpha: float = 0.05,
    alternative: Alternative | str = Alternative.TWO_SIDED,
    confidence_level: float | None = None,
    seed: int | None = None,
) -> StatisticalResult:
    """Test z asymptotique pour deux proportions indépendantes (effet orienté B - A)."""
    validate_alpha(alpha)
    alt = normalize_alternative(alternative)
    conf_level = 1.0 - alpha if confidence_level is None else confidence_level
    validate_confidence_level(conf_level)

    arr_a, arr_b, n_excluded = _extract_binary_arrays(group_a, group_b)

    n_a = int(arr_a.size)
    n_b = int(arr_b.size)
    succ_a = int(np.sum(arr_a))
    succ_b = int(np.sum(arr_b))
    fail_a = n_a - succ_a
    fail_b = n_b - succ_b

    rate_a = succ_a / n_a
    rate_b = succ_b / n_b
    diff = rate_b - rate_a

    # Proportion poolée sous H0
    pooled_p = (succ_a + succ_b) / (n_a + n_b)
    pooled_se = math.sqrt(pooled_p * (1.0 - pooled_p) * (1.0 / n_a + 1.0 / n_b))

    if pooled_se == 0.0:
        raise DegenerateSampleError(
            "DEGENERATE_SAMPLE",
            "La variance poolée est nulle ; le test z est indéfini.",
            details={"succ_a": succ_a, "succ_b": succ_b, "n_a": n_a, "n_b": n_b},
        )

    z_stat = diff / pooled_se

    # Calcul de la p-value
    if alt is Alternative.GREATER:
        p_val = float(stats.norm.sf(z_stat))
    elif alt is Alternative.LESS:
        p_val = float(stats.norm.cdf(z_stat))
    else:
        p_val = float(2.0 * stats.norm.sf(abs(z_stat)))

    ci = unpooled_proportion_ci(rate_a, n_a, rate_b, n_b, confidence_level=conf_level)
    effect = build_cohens_h(rate_a, rate_b)
    rel_lift = (rate_b - rate_a) / rate_a if rate_a > 0 else None

    # Hypothèses de validité
    min_event = min(succ_a, fail_a, succ_b, fail_b)
    normal_approx_status = (
        AssumptionStatus.SATISFIED if min_event >= 10 else AssumptionStatus.VIOLATED
    )

    assumptions = (
        Assumption(
            code="INDEPENDENCE",
            description="Les observations sont indépendantes entre et au sein des groupes.",
            status=AssumptionStatus.UNVERIFIABLE,
            detail="Dépend du protocole d'assignation aléatoire.",
        ),
        Assumption(
            code="BINARY_OUTCOME",
            description="La variable mesurée est strictement binaire (succès / échec).",
            status=AssumptionStatus.SATISFIED,
        ),
        Assumption(
            code="NORMAL_APPROXIMATION",
            description="Le nombre d'événements attendus par groupe est suffisant (>= 10).",
            status=normal_approx_status,
            detail=f"Nombre minimal d'événements observé : {min_event}.",
        ),
    )

    warnings: list[AnalysisWarning] = []
    if min_event < 10:
        warnings.append(
            AnalysisWarning(
                code="LOW_EVENT_COUNT",
                severity=Severity.WARNING,
                message=(
                    f"Le décompte minimal d'événements ({min_event}) est inférieur à 10. "
                    "L'approximation normale peut être imprécise ; Fisher exact est recommandé."
                ),
                suggested_alternative=Method.FISHER_EXACT,
            )
        )

    decision = Decision.REJECT_NULL if p_val <= alpha else Decision.FAIL_TO_REJECT_NULL

    null_text = "Le taux de conversion de B est égal à celui de A."
    if alt is Alternative.GREATER:
        alt_text = "Le taux de conversion de B est supérieur à celui de A."
    elif alt is Alternative.LESS:
        alt_text = "Le taux de conversion de B est inférieur à celui de A."
    else:
        alt_text = "Les taux de conversion de A et B sont différents."

    return StatisticalResult(
        method=Method.TWO_PROPORTION_Z,
        metric_type=MetricType.BINARY,
        hypotheses=Hypotheses(
            alternative=alt,
            null_text=null_text,
            alternative_text=alt_text,
        ),
        groups=Groups(
            a=GroupSummary(n=n_a, successes=succ_a, rate=rate_a),
            b=GroupSummary(n=n_b, successes=succ_b, rate=rate_b),
        ),
        statistic=Statistic(name="z", value=float(z_stat)),
        alpha=alpha,
        decision=decision,
        estimate=Estimate(
            name=EstimateName.DIFFERENCE_OF_PROPORTIONS,
            value=float(diff),
            unit=UNIT_PROPORTION,
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


def fisher_exact(
    group_a: Any,
    group_b: Any,
    *,
    alpha: float = 0.05,
    alternative: Alternative | str = Alternative.TWO_SIDED,
    confidence_level: float | None = None,
    seed: int | None = None,
) -> StatisticalResult:
    """Test exact de Fisher sur tableau de contingence 2x2."""
    validate_alpha(alpha)
    alt = normalize_alternative(alternative)
    conf_level = 1.0 - alpha if confidence_level is None else confidence_level
    validate_confidence_level(conf_level)

    arr_a, arr_b, n_excluded = _extract_binary_arrays(group_a, group_b)

    n_a = int(arr_a.size)
    n_b = int(arr_b.size)
    succ_a = int(np.sum(arr_a))
    succ_b = int(np.sum(arr_b))
    fail_a = n_a - succ_a
    fail_b = n_b - succ_b

    rate_a = succ_a / n_a
    rate_b = succ_b / n_b
    diff = rate_b - rate_a

    # Tableau avec B en ligne 1 pour cohérence d'orientation B - A
    table = [[succ_b, fail_b], [succ_a, fail_a]]

    scipy_alt = to_scipy_alternative(alt)
    res = stats.fisher_exact(table, alternative=scipy_alt)
    odds_ratio_stat = float(res.statistic) if math.isfinite(res.statistic) else None
    p_val = float(res.pvalue)

    # IC Newcombe pour la différence de proportions
    ci = newcombe_proportion_ci(rate_a, n_a, rate_b, n_b, confidence_level=conf_level)
    effect = build_cohens_h(rate_a, rate_b)
    rel_lift = (rate_b - rate_a) / rate_a if rate_a > 0 else None

    assumptions = (
        Assumption(
            code="INDEPENDENCE",
            description="Les observations sont indépendantes entre et au sein des groupes.",
            status=AssumptionStatus.UNVERIFIABLE,
            detail="Dépend du protocole expérimental.",
        ),
        Assumption(
            code="BINARY_OUTCOME",
            description="La variable mesurée est strictement binaire.",
            status=AssumptionStatus.SATISFIED,
        ),
        Assumption(
            code="FIXED_MARGINALS",
            description="Test conditionnel exact, valide même pour de très faibles effectifs.",
            status=AssumptionStatus.SATISFIED,
        ),
    )

    warnings: list[AnalysisWarning] = []
    if odds_ratio_stat is None:
        warnings.append(
            AnalysisWarning(
                code="ZERO_CELL_COUNT",
                severity=Severity.INFO,
                message="Au moins une cellule du tableau est à zéro ; l'odds ratio est infini ou indéfini.",
            )
        )

    decision = Decision.REJECT_NULL if p_val <= alpha else Decision.FAIL_TO_REJECT_NULL

    null_text = "L'odds ratio de B par rapport à A est égal à 1 (taux identiques)."
    if alt is Alternative.GREATER:
        alt_text = "L'odds ratio de B par rapport à A est supérieur à 1."
    elif alt is Alternative.LESS:
        alt_text = "L'odds ratio de B par rapport à A est inférieur à 1."
    else:
        alt_text = "L'odds ratio de B par rapport à A est différent de 1."

    return StatisticalResult(
        method=Method.FISHER_EXACT,
        metric_type=MetricType.BINARY,
        hypotheses=Hypotheses(
            alternative=alt,
            null_text=null_text,
            alternative_text=alt_text,
        ),
        groups=Groups(
            a=GroupSummary(n=n_a, successes=succ_a, rate=rate_a),
            b=GroupSummary(n=n_b, successes=succ_b, rate=rate_b),
        ),
        statistic=Statistic(name="odds_ratio", value=odds_ratio_stat),
        alpha=alpha,
        decision=decision,
        estimate=Estimate(
            name=EstimateName.DIFFERENCE_OF_PROPORTIONS,
            value=float(diff),
            unit=UNIT_PROPORTION,
        ),
        confidence_interval=ci,
        effect_size=effect,
        reproducibility=build_reproducibility(arr_a, arr_b, seed=seed),
        p_value=p_val,
        p_value_source=PValueSource.EXACT,
        relative_lift=rel_lift,
        n_excluded=n_excluded,
        assumptions=assumptions,
        warnings=tuple(warnings),
    )
