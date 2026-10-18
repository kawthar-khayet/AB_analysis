"""Constructions réutilisables d'intervalles de confiance pour A/B testing.

Toutes les fonctions construisent l'intervalle pour la différence B - A.
La méthode employée est explicitement déclarée dans chaque :class:`ConfidenceInterval`.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats

from ab_stats.analyses._common import validate_confidence_level
from ab_stats.exceptions import InvalidParameterError
from ab_stats.results import CIMethod, ConfidenceInterval

__all__ = [
    "unpooled_proportion_ci",
    "newcombe_proportion_ci",
    "welch_mean_ci",
    "student_mean_ci",
    "hodges_lehmann_ci",
    "percentile_bootstrap_ci",
]


def unpooled_proportion_ci(
    rate_a: float,
    n_a: int,
    rate_b: float,
    n_b: int,
    *,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Intervalle de Wald non-poolé pour la différence de deux proportions (B - A)."""
    validate_confidence_level(confidence_level)
    diff = rate_b - rate_a
    variance = (rate_a * (1.0 - rate_a) / n_a) + (rate_b * (1.0 - rate_b) / n_b)
    se = math.sqrt(max(0.0, variance))
    alpha = 1.0 - confidence_level
    z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
    lower = diff - z_crit * se
    upper = diff + z_crit * se
    return ConfidenceInterval(
        level=confidence_level,
        lower=lower,
        upper=upper,
        method=CIMethod.NORMAL_APPROX_UNPOOLED,
    )


def _wilson_score_interval(rate: float, n: int, confidence_level: float) -> tuple[float, float]:
    """Intervalle de score de Wilson pour une proportion individuelle."""
    alpha = 1.0 - confidence_level
    z = float(stats.norm.ppf(1.0 - alpha / 2.0))
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (rate + z2 / (2 * n)) / denom
    margin = (z * math.sqrt((rate * (1.0 - rate) / n) + (z2 / (4 * n * n)))) / denom
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return lower, upper


def newcombe_proportion_ci(
    rate_a: float,
    n_a: int,
    rate_b: float,
    n_b: int,
    *,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Intervalle hybride de Newcombe (méthode 10 sans correction de continuité) pour B - A.

    Recommandé en complément de Fisher exact, qui ne produit pas d'IC direct
    sur la différence de proportions.
    """
    validate_confidence_level(confidence_level)
    l1, u1 = _wilson_score_interval(rate_a, n_a, confidence_level)
    l2, u2 = _wilson_score_interval(rate_b, n_b, confidence_level)
    diff = rate_b - rate_a

    lower = diff - math.sqrt((rate_b - l2) ** 2 + (u1 - rate_a) ** 2)
    upper = diff + math.sqrt((u2 - rate_b) ** 2 + (rate_a - l1) ** 2)

    return ConfidenceInterval(
        level=confidence_level,
        lower=max(-1.0, lower),
        upper=min(1.0, upper),
        method=CIMethod.NEWCOMBE,
    )


def welch_mean_ci(
    mean_a: float,
    sd_a: float,
    n_a: int,
    mean_b: float,
    sd_b: float,
    n_b: int,
    *,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Intervalle t de Welch (variances inégales) pour la différence de moyennes B - A."""
    validate_confidence_level(confidence_level)
    diff = mean_b - mean_a
    va = (sd_a**2) / n_a
    vb = (sd_b**2) / n_b
    variance_sum = va + vb

    if variance_sum <= 0.0:
        return ConfidenceInterval(
            level=confidence_level,
            lower=diff,
            upper=diff,
            method=CIMethod.WELCH_T_DIST,
        )

    # Degrés de liberté de Welch-Satterthwaite
    num = variance_sum**2
    denom = (va**2) / (n_a - 1) + (vb**2) / (n_b - 1)
    df = num / denom if denom > 0 else float(n_a + n_b - 2)

    se = math.sqrt(variance_sum)
    alpha = 1.0 - confidence_level
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=df))

    return ConfidenceInterval(
        level=confidence_level,
        lower=diff - t_crit * se,
        upper=diff + t_crit * se,
        method=CIMethod.WELCH_T_DIST,
    )


def student_mean_ci(
    mean_a: float,
    sd_a: float,
    n_a: int,
    mean_b: float,
    sd_b: float,
    n_b: int,
    *,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Intervalle t de Student (variances égales supposées) pour la différence de moyennes B - A."""
    validate_confidence_level(confidence_level)
    diff = mean_b - mean_a
    df = n_a + n_b - 2
    if df <= 0:
        raise InvalidParameterError(
            "INSUFFICIENT_SAMPLE_SIZE",
            "Au moins 3 observations au total sont requises.",
        )

    pooled_variance = ((n_a - 1) * (sd_a**2) + (n_b - 1) * (sd_b**2)) / df
    se = math.sqrt(pooled_variance * (1.0 / n_a + 1.0 / n_b))

    alpha = 1.0 - confidence_level
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=df))

    return ConfidenceInterval(
        level=confidence_level,
        lower=diff - t_crit * se,
        upper=diff + t_crit * se,
        method=CIMethod.STUDENT_T_DIST,
    )


def hodges_lehmann_ci(
    group_a: Any,
    group_b: Any,
    *,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Intervalle de confiance non-paramétrique pour l'estimateur de Hodges-Lehmann (B - A)."""
    validate_confidence_level(confidence_level)
    arr_a = np.asarray(group_a, dtype=float)
    arr_b = np.asarray(group_b, dtype=float)
    n_a = arr_a.size
    n_b = arr_b.size

    # Différences deux à deux b_j - a_i
    diffs = np.sort((arr_b[:, np.newaxis] - arr_a[np.newaxis, :]).ravel())
    total_pairs = diffs.size

    # Approximation normale du rang critique pour le test de Wilcoxon-Mann-Whitney
    mean_rank = (n_a * n_b) / 2.0
    sd_rank = math.sqrt((n_a * n_b * (n_a + n_b + 1.0)) / 12.0)
    alpha = 1.0 - confidence_level
    z = float(stats.norm.ppf(1.0 - alpha / 2.0))

    k = int(math.floor(mean_rank - z * sd_rank))
    # Bornes dans [0, total_pairs - 1]
    lower_idx = max(0, min(k, total_pairs - 1))
    upper_idx = max(0, min(total_pairs - 1 - k, total_pairs - 1))

    return ConfidenceInterval(
        level=confidence_level,
        lower=float(diffs[lower_idx]),
        upper=float(diffs[upper_idx]),
        method=CIMethod.HODGES_LEHMANN,
    )


def percentile_bootstrap_ci(
    resampled_differences: np.ndarray,
    *,
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    """Intervalle bootstrap par percentiles sur la distribution des différences rééchantillonnées."""
    validate_confidence_level(confidence_level)
    diffs = np.asarray(resampled_differences, dtype=float)
    if diffs.size < 100:
        raise InvalidParameterError(
            "INSUFFICIENT_BOOTSTRAP_RESAMPLES",
            "Au moins 100 rééchantillonnages sont nécessaires pour un intervalle percentile.",
            details={"count": int(diffs.size)},
        )
    alpha = 1.0 - confidence_level
    lower_p = 100.0 * (alpha / 2.0)
    upper_p = 100.0 * (1.0 - alpha / 2.0)
    lower = float(np.percentile(diffs, lower_p))
    upper = float(np.percentile(diffs, upper_p))
    return ConfidenceInterval(
        level=confidence_level,
        lower=lower,
        upper=upper,
        method=CIMethod.PERCENTILE_BOOTSTRAP,
    )
