"""Tailles d'effet standardisées et conventions associées.

Ce module calcule les mesures d'effet sans unité, adaptées à chaque famille :
* ``cohens_h`` pour les proportions (métriques binaires).
* ``cohens_d`` et ``hedges_g`` pour les moyennes (métriques continues paramétriques).
* ``cliffs_delta`` pour les rangs (métriques ordinales ou continues non paramétriques).

Chaque étiquette qualitative (``NEGLIGIBLE``, ``SMALL``, ``MEDIUM``, ``LARGE``) est
toujours appariée à sa convention explicite.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats

from ab_stats.exceptions import InvalidParameterError
from ab_stats.results import EffectSize, EffectSizeLabel, EffectSizeName

__all__ = [
    "cohens_h",
    "cohens_d",
    "hedges_g",
    "cliffs_delta",
    "label_cohens_h",
    "label_cohens_d",
    "label_cliffs_delta",
    "build_cohens_h",
    "build_cohens_d",
    "build_hedges_g",
    "build_cliffs_delta",
]

CONVENTION_COHEN_1988 = "cohen_1988"
CONVENTION_HEDGES_1981 = "hedges_1981"
CONVENTION_ROMANO_2006 = "romano_2006"


def _check_probability(p: float, name: str) -> None:
    if not (0.0 <= p <= 1.0 and math.isfinite(p)):
        raise InvalidParameterError(
            "INVALID_PROPORTION",
            f"La proportion {name} doit être comprise entre 0 et 1, reçu {p}.",
            details={"parameter": name, "value": p},
        )


def cohens_h(prop_a: float, prop_b: float) -> float:
    """Calcule le h de Cohen pour la différence de deux proportions (B - A).

    h = 2 * arcsin(sqrt(p_B)) - 2 * arcsin(sqrt(p_A))
    """
    _check_probability(prop_a, "prop_a")
    _check_probability(prop_b, "prop_b")
    phi_a = 2.0 * math.asin(math.sqrt(prop_a))
    phi_b = 2.0 * math.asin(math.sqrt(prop_b))
    return phi_b - phi_a


def cohens_d(
    mean_a: float,
    mean_b: float,
    sd_a: float,
    sd_b: float,
    n_a: int,
    n_b: int,
) -> float:
    """Calcule le d de Cohen pour deux groupes indépendants (B - A)."""
    if n_a < 2 or n_b < 2:
        raise InvalidParameterError(
            "INSUFFICIENT_SAMPLE_SIZE",
            "Chaque groupe doit contenir au moins 2 observations pour estimer la variance.",
            details={"n_a": n_a, "n_b": n_b},
        )
    df = n_a + n_b - 2
    pooled_variance = ((n_a - 1) * (sd_a**2) + (n_b - 1) * (sd_b**2)) / df
    if pooled_variance <= 0.0:
        return 0.0 if mean_b == mean_a else float("inf")
    pooled_sd = math.sqrt(pooled_variance)
    return (mean_b - mean_a) / pooled_sd


def hedges_g(
    d: float,
    n_a: int,
    n_b: int,
) -> float:
    """Corrige le d de Cohen pour les petits effectifs (Hedges' g)."""
    df = n_a + n_b - 2
    if df <= 0:
        return d
    # Facteur de correction approché de Hedges (1981)
    correction = 1.0 - (3.0 / (4.0 * df - 1.0))
    return d * correction


def cliffs_delta(group_a: Any, group_b: Any) -> float:
    """Calcule le delta de Cliff entre B et A: P(B > A) - P(B < A)."""
    arr_a = np.asarray(group_a, dtype=float)
    arr_b = np.asarray(group_b, dtype=float)
    n_a = arr_a.size
    n_b = arr_b.size
    if n_a == 0 or n_b == 0:
        raise InvalidParameterError(
            "EMPTY_GROUP",
            "Les deux groupes doivent être non vides pour calculer le delta de Cliff.",
            details={"n_a": n_a, "n_b": n_b},
        )

    # Calcul vectorisé
    diffs = arr_b[:, np.newaxis] - arr_a[np.newaxis, :]
    n_gt = np.sum(diffs > 0)
    n_lt = np.sum(diffs < 0)
    return float((n_gt - n_lt) / (n_a * n_b))


def label_cohens_h(value: float) -> EffectSizeLabel:
    """Étiquette selon Cohen (1988) : <0.2 négligeable, 0.2-0.5 petit, 0.5-0.8 moyen, >=0.8 grand."""
    abs_val = abs(value)
    if abs_val < 0.2:
        return EffectSizeLabel.NEGLIGIBLE
    if abs_val < 0.5:
        return EffectSizeLabel.SMALL
    if abs_val < 0.8:
        return EffectSizeLabel.MEDIUM
    return EffectSizeLabel.LARGE


def label_cohens_d(value: float) -> EffectSizeLabel:
    """Étiquette selon Cohen (1988) : <0.2 négligeable, 0.2-0.5 petit, 0.5-0.8 moyen, >=0.8 grand."""
    abs_val = abs(value)
    if abs_val < 0.2:
        return EffectSizeLabel.NEGLIGIBLE
    if abs_val < 0.5:
        return EffectSizeLabel.SMALL
    if abs_val < 0.8:
        return EffectSizeLabel.MEDIUM
    return EffectSizeLabel.LARGE


def label_cliffs_delta(value: float) -> EffectSizeLabel:
    """Étiquette selon Romano et al. (2006) : <0.147 négligeable, 0.147-0.33 petit, 0.33-0.474 moyen, >=0.474 grand."""
    abs_val = abs(value)
    if abs_val < 0.147:
        return EffectSizeLabel.NEGLIGIBLE
    if abs_val < 0.33:
        return EffectSizeLabel.SMALL
    if abs_val < 0.474:
        return EffectSizeLabel.MEDIUM
    return EffectSizeLabel.LARGE


def build_cohens_h(prop_a: float, prop_b: float) -> EffectSize:
    val = cohens_h(prop_a, prop_b)
    return EffectSize(
        name=EffectSizeName.COHENS_H,
        value=val,
        convention=CONVENTION_COHEN_1988,
        label=label_cohens_h(val),
    )


def build_cohens_d(
    mean_a: float,
    mean_b: float,
    sd_a: float,
    sd_b: float,
    n_a: int,
    n_b: int,
) -> EffectSize:
    val = cohens_d(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
    return EffectSize(
        name=EffectSizeName.COHENS_D,
        value=val,
        convention=CONVENTION_COHEN_1988,
        label=label_cohens_d(val),
    )


def build_hedges_g(
    mean_a: float,
    mean_b: float,
    sd_a: float,
    sd_b: float,
    n_a: int,
    n_b: int,
) -> EffectSize:
    d = cohens_d(mean_a, mean_b, sd_a, sd_b, n_a, n_b)
    val = hedges_g(d, n_a, n_b)
    return EffectSize(
        name=EffectSizeName.HEDGES_G,
        value=val,
        convention=CONVENTION_HEDGES_1981,
        label=label_cohens_d(val),
    )


def build_cliffs_delta(group_a: Any, group_b: Any) -> EffectSize:
    val = cliffs_delta(group_a, group_b)
    return EffectSize(
        name=EffectSizeName.CLIFFS_DELTA,
        value=val,
        convention=CONVENTION_ROMANO_2006,
        label=label_cliffs_delta(val),
    )
