"""Diagnostics : décrire les données avant de choisir une méthode.

Ce module ne juge pas, il **décrit et signale**. Il produit deux choses :

* des statistiques descriptives par groupe — effectifs, taux ou moyennes,
  dispersion, quartiles, asymétrie, valeurs extrêmes ;
* des **constats** (:class:`~ab_stats.results.AnalysisWarning`) sur la qualité
  statistique des données : trop peu d'événements, échantillon petit, forte
  asymétrie, valeurs extrêmes, variances très différentes, groupe constant,
  groupes déséquilibrés.

Ces constats ne mentionnent aucune méthode. C'est ``compatibility.py``
(étape 8) qui les traduira en avertissements par méthode, avec une alternative
suggérée. Le partage des rôles est donc :

``data.py``           → intégrité des données (ce qui a été écarté, et pourquoi)
``diagnostics.py``    → qualité statistique (ce que valent les données retenues)
``compatibility.py``  → conséquences par méthode (ce qu'on a le droit d'utiliser)

Pourquoi les diagnostics viennent avant le choix de la méthode : un test n'est
valable que si ses hypothèses sont crédibles pour ces données-là. Et sans les
effectifs, un pourcentage est ininterprétable.

Statistiques descriptives inspirées du module ``descriptive`` d'ExperimentOS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Union

import numpy as np
from scipy import stats

from ab_stats.data import NormalizedDataset
from ab_stats.exceptions import InvalidParameterError
from ab_stats.results import (
    AnalysisWarning,
    CIMethod,
    ConfidenceInterval,
    MetricType,
    Severity,
)

__all__ = [
    "DEFAULT_CONFIDENCE_LEVEL",
    "DEFAULT_OUTLIER_IQR_MULTIPLIER",
    "OUTLIER_RATE_THRESHOLD",
    "MIN_EVENT_COUNT",
    "SMALL_SAMPLE_THRESHOLD",
    "HIGH_SKEWNESS_THRESHOLD",
    "VARIANCE_RATIO_THRESHOLD",
    "BALANCE_THRESHOLD",
    "BinaryGroupDiagnostics",
    "ContinuousGroupDiagnostics",
    "GroupDiagnostics",
    "BinaryComparison",
    "ContinuousComparison",
    "Balance",
    "Diagnostics",
    "diagnose",
]


#: Niveau des intervalles descriptifs affichés sur la page Diagnostics.
DEFAULT_CONFIDENCE_LEVEL = 0.95

#: Règle des valeurs extrêmes : au-delà de k écarts interquartiles des quartiles.
#: C'est une convention, pas une vérité : elle est déclarée dans la sortie.
DEFAULT_OUTLIER_IQR_MULTIPLIER = 1.5

#: Part de valeurs extrêmes au-delà de laquelle on avertit. La règle
#: 1,5 x IQR en marque déjà environ 0,7 % sur des données parfaitement
#: normales : avertir dès la première serait du bruit permanent.
OUTLIER_RATE_THRESHOLD = 0.02

#: En dessous, l'approximation normale du z-test devient douteuse.
MIN_EVENT_COUNT = 10

#: En dessous, le théorème central limite ne protège plus les t-tests.
SMALL_SAMPLE_THRESHOLD = 30

#: Au-delà en valeur absolue, la distribution est nettement asymétrique.
HIGH_SKEWNESS_THRESHOLD = 1.0

#: Rapport des variances au-delà duquel on les dit très différentes.
#: 4 correspond à un rapport d'écarts-types de 2.
VARIANCE_RATIO_THRESHOLD = 4.0

#: En dessous de ce rapport d'effectifs, la randomisation paraît suspecte.
BALANCE_THRESHOLD = 0.8


# ---------------------------------------------------------------------------
# Statistiques par groupe
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BinaryGroupDiagnostics:
    """Description d'un groupe pour une métrique binaire."""

    label: str
    n: int
    successes: int
    failures: int
    rate: float
    standard_error: float
    rate_ci: ConfidenceInterval

    @property
    def has_variation(self) -> bool:
        """Faux si tout le groupe a converti, ou si personne n'a converti."""
        return 0 < self.successes < self.n


@dataclass(frozen=True, slots=True)
class ContinuousGroupDiagnostics:
    """Description d'un groupe pour une métrique continue.

    ``skewness`` est l'asymétrie ajustée (g1 corrigée du biais). Elle vaut
    ``None`` en dessous de trois observations, où elle n'a pas de sens.
    """

    label: str
    n: int
    mean: float
    median: float
    variance: float
    standard_deviation: float
    standard_error: float
    minimum: float
    maximum: float
    q1: float
    q3: float
    iqr: float
    skewness: float | None
    n_outliers: int
    outlier_bounds: tuple[float, float] | None
    mean_ci: ConfidenceInterval

    @property
    def has_variation(self) -> bool:
        """Faux si toutes les observations du groupe sont identiques."""
        return self.standard_deviation > 0

    @property
    def outlier_rate(self) -> float:
        """Part des observations hors des bornes de la règle des quartiles."""
        return self.n_outliers / self.n


GroupDiagnostics = Union[BinaryGroupDiagnostics, ContinuousGroupDiagnostics]


# ---------------------------------------------------------------------------
# Comparaisons et équilibre
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BinaryComparison:
    """Écarts descriptifs entre A et B, toujours dans le sens B − A.

    Ce sont des **descriptions**, pas des estimations avec incertitude : aucun
    intervalle, aucune p-value. L'analyse viendra plus tard.
    """

    absolute_difference: float
    relative_lift: float | None
    risk_ratio: float | None
    odds_ratio: float | None


@dataclass(frozen=True, slots=True)
class ContinuousComparison:
    """Écarts descriptifs entre A et B, toujours dans le sens B − A."""

    mean_difference: float
    median_difference: float
    variance_ratio: float | None


@dataclass(frozen=True, slots=True)
class Balance:
    """Équilibre des effectifs entre les deux groupes."""

    n_a: int
    n_b: int
    ratio: float
    """Effectif du plus petit groupe divisé par celui du plus grand, dans ]0, 1]."""


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Tout ce qu'on sait des données avant de choisir une méthode."""

    metric_type: MetricType
    unit: str
    group_a: GroupDiagnostics
    group_b: GroupDiagnostics
    comparison: BinaryComparison | ContinuousComparison
    balance: Balance
    n_input: int
    n_retained: int
    n_excluded: int
    confidence_level: float
    outlier_iqr_multiplier: float
    outlier_rate_threshold: float
    warnings: tuple[AnalysisWarning, ...]

    @property
    def codes(self) -> frozenset[str]:
        """Codes des constats émis, pour un test ou un filtrage rapide."""
        return frozenset(warning.code for warning in self.warnings)


# ---------------------------------------------------------------------------
# Calculs
# ---------------------------------------------------------------------------


def _check_unit_interval(value: float, parameter: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InvalidParameterError(
            "INVALID_DIAGNOSTIC_PARAMETER",
            "Ce paramètre doit être un nombre.",
            details={"parameter": parameter, "value": value},
        )
    if not 0.0 < value < 1.0:
        raise InvalidParameterError(
            "INVALID_DIAGNOSTIC_PARAMETER",
            "Ce paramètre doit être strictement compris entre 0 et 1.",
            details={"parameter": parameter, "value": value},
        )


def _check_positive(value: float, parameter: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise InvalidParameterError(
            "INVALID_DIAGNOSTIC_PARAMETER",
            "Ce paramètre doit être strictement positif.",
            details={"parameter": parameter, "value": value},
        )


def _skewness(values: np.ndarray) -> float | None:
    """Asymétrie ajustée g1, ou ``None`` si elle n'est pas définie.

    Positive : une longue traîne à droite (montants de panier). Négative :
    longue traîne à gauche. Proche de 0 : distribution symétrique.
    """
    n = values.size
    if n < 3:
        return None
    centered = values - values.mean()
    m2 = float((centered**2).mean())
    if m2 == 0:
        return None
    m3 = float((centered**3).mean())
    biased = m3 / m2**1.5
    return biased * math.sqrt(n * (n - 1)) / (n - 2)


def _proportion_ci(rate: float, n: int, *, level: float) -> ConfidenceInterval:
    """Intervalle de Wald pour une proportion, borné à [0, 1]."""
    z = float(stats.norm.ppf(0.5 + level / 2))
    half_width = z * math.sqrt(rate * (1 - rate) / n)
    return ConfidenceInterval(
        level=level,
        lower=max(0.0, rate - half_width),
        upper=min(1.0, rate + half_width),
        method=CIMethod.WALD,
    )


def _mean_ci(values: np.ndarray, *, level: float) -> ConfidenceInterval:
    """Intervalle de Student pour une moyenne ; indisponible si n < 2."""
    n = values.size
    if n < 2:
        return ConfidenceInterval(level=level)
    standard_error = float(values.std(ddof=1)) / math.sqrt(n)
    if standard_error == 0:
        mean = float(values.mean())
        return ConfidenceInterval(
            level=level, lower=mean, upper=mean, method=CIMethod.STUDENT_T_DIST
        )
    half_width = float(stats.t.ppf(0.5 + level / 2, df=n - 1)) * standard_error
    mean = float(values.mean())
    return ConfidenceInterval(
        level=level,
        lower=mean - half_width,
        upper=mean + half_width,
        method=CIMethod.STUDENT_T_DIST,
    )


def _ratio(numerator: float, denominator: float) -> float | None:
    """Rapport, ou ``None`` quand le dénominateur est nul."""
    return None if denominator == 0 else numerator / denominator


def _odds(rate: float) -> float | None:
    """Cote d'une proportion, indéfinie quand le taux vaut 1."""
    return None if rate >= 1 else rate / (1 - rate)


def _binary_group(values: np.ndarray, *, label: str, level: float) -> BinaryGroupDiagnostics:
    n = int(values.size)
    successes = int(values.sum())
    rate = successes / n
    return BinaryGroupDiagnostics(
        label=label,
        n=n,
        successes=successes,
        failures=n - successes,
        rate=rate,
        standard_error=math.sqrt(rate * (1 - rate) / n),
        rate_ci=_proportion_ci(rate, n, level=level),
    )


def _continuous_group(
    values: np.ndarray,
    *,
    label: str,
    level: float,
    iqr_multiplier: float,
) -> ContinuousGroupDiagnostics:
    n = int(values.size)
    standard_deviation = float(values.std(ddof=1)) if n > 1 else 0.0
    q1, q3 = (float(value) for value in np.quantile(values, [0.25, 0.75]))
    iqr = q3 - q1

    if iqr > 0:
        bounds = (q1 - iqr_multiplier * iqr, q3 + iqr_multiplier * iqr)
        n_outliers = int(((values < bounds[0]) | (values > bounds[1])).sum())
    else:
        bounds = None
        n_outliers = 0

    return ContinuousGroupDiagnostics(
        label=label,
        n=n,
        mean=float(values.mean()),
        median=float(np.median(values)),
        variance=float(values.var(ddof=1)) if n > 1 else 0.0,
        standard_deviation=standard_deviation,
        standard_error=standard_deviation / math.sqrt(n),
        minimum=float(values.min()),
        maximum=float(values.max()),
        q1=q1,
        q3=q3,
        iqr=iqr,
        skewness=_skewness(values),
        n_outliers=n_outliers,
        outlier_bounds=bounds,
        mean_ci=_mean_ci(values, level=level),
    )


# ---------------------------------------------------------------------------
# Constats
# ---------------------------------------------------------------------------


def _warn(code: str, message: str, field: str, severity: Severity = Severity.WARNING) -> AnalysisWarning:
    return AnalysisWarning(code=code, severity=severity, message=message, affected_field=field)


def _binary_warnings(
    groups: tuple[BinaryGroupDiagnostics, BinaryGroupDiagnostics],
    *,
    min_event_count: int,
) -> list[AnalysisWarning]:
    warnings: list[AnalysisWarning] = []
    for group in groups:
        field = f"group_{group.label.lower()}"
        if not group.has_variation:
            warnings.append(
                _warn(
                    "ZERO_VARIANCE",
                    f"Le groupe {group.label} est constant : "
                    f"{group.successes} succès sur {group.n} observations.",
                    field,
                    Severity.CRITICAL,
                )
            )
        elif min(group.successes, group.failures) < min_event_count:
            warnings.append(
                _warn(
                    "LOW_EVENT_COUNT",
                    f"Le groupe {group.label} ne compte que {group.successes} succès et "
                    f"{group.failures} échecs (minimum recommandé : {min_event_count}).",
                    field,
                )
            )
    return warnings


def _continuous_warnings(
    groups: tuple[ContinuousGroupDiagnostics, ContinuousGroupDiagnostics],
    *,
    variance_ratio: float | None,
    skewness_threshold: float,
    variance_ratio_threshold: float,
    outlier_rate_threshold: float,
) -> list[AnalysisWarning]:
    warnings: list[AnalysisWarning] = []
    for group in groups:
        field = f"group_{group.label.lower()}"
        if not group.has_variation:
            warnings.append(
                _warn(
                    "ZERO_VARIANCE",
                    f"Le groupe {group.label} est constant : toutes les observations "
                    f"valent {group.mean:g}.",
                    field,
                    Severity.CRITICAL,
                )
            )
            continue
        if group.skewness is not None and abs(group.skewness) > skewness_threshold:
            direction = "à droite" if group.skewness > 0 else "à gauche"
            warnings.append(
                _warn(
                    "HIGH_SKEWNESS",
                    f"Le groupe {group.label} est nettement asymétrique {direction} "
                    f"(asymétrie {group.skewness:.2f}).",
                    field,
                )
            )
        if group.outlier_rate > outlier_rate_threshold:
            warnings.append(
                _warn(
                    "OUTLIERS_DETECTED",
                    f"{group.n_outliers} valeur(s) extrême(s) dans le groupe {group.label} "
                    f"({group.outlier_rate:.1%}), hors de l'intervalle "
                    f"[{group.outlier_bounds[0]:.4g} ; {group.outlier_bounds[1]:.4g}].",
                    field,
                )
            )

    if variance_ratio is not None and variance_ratio > variance_ratio_threshold:
        warnings.append(
            _warn(
                "UNEQUAL_VARIANCES",
                f"Les variances des deux groupes diffèrent d'un facteur "
                f"{variance_ratio:.1f} (seuil : {variance_ratio_threshold:g}).",
                "groups",
            )
        )
    return warnings


def _shared_warnings(
    group_a: GroupDiagnostics,
    group_b: GroupDiagnostics,
    balance: Balance,
    *,
    small_sample: int,
    balance_threshold: float,
) -> list[AnalysisWarning]:
    warnings: list[AnalysisWarning] = []
    for group in (group_a, group_b):
        if group.n < small_sample:
            warnings.append(
                _warn(
                    "SMALL_SAMPLE",
                    f"Le groupe {group.label} ne compte que {group.n} observations "
                    f"(seuil : {small_sample}).",
                    f"group_{group.label.lower()}",
                )
            )
    if balance.ratio < balance_threshold:
        warnings.append(
            _warn(
                "UNBALANCED_GROUPS",
                f"Les effectifs sont très inégaux : {balance.n_a} contre {balance.n_b} "
                f"(rapport {balance.ratio:.2f}). La randomisation mérite une vérification.",
                "groups",
            )
        )
    return warnings


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def diagnose(
    dataset: NormalizedDataset,
    *,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    outlier_iqr_multiplier: float = DEFAULT_OUTLIER_IQR_MULTIPLIER,
    min_event_count: int = MIN_EVENT_COUNT,
    small_sample: int = SMALL_SAMPLE_THRESHOLD,
    skewness_threshold: float = HIGH_SKEWNESS_THRESHOLD,
    variance_ratio_threshold: float = VARIANCE_RATIO_THRESHOLD,
    outlier_rate_threshold: float = OUTLIER_RATE_THRESHOLD,
    balance_threshold: float = BALANCE_THRESHOLD,
) -> Diagnostics:
    """Décrit un jeu de données normalisé et signale ce qui mérite attention.

    Args:
        dataset: sortie de :func:`ab_stats.data.normalize`.
        confidence_level: niveau des intervalles descriptifs par groupe.
        outlier_iqr_multiplier: règle des valeurs extrêmes, en écarts
            interquartiles au-delà des quartiles.
        min_event_count: succès et échecs minimaux par groupe (binaire).
        small_sample: effectif en dessous duquel un groupe est dit petit.
        skewness_threshold: asymétrie absolue au-delà de laquelle on avertit.
        variance_ratio_threshold: rapport de variances au-delà duquel on avertit.
        outlier_rate_threshold: part de valeurs extrêmes au-delà de laquelle on
            avertit. La règle des quartiles en marque déjà environ 0,7 % sur des
            données normales : avertir dès la première serait du bruit.
        balance_threshold: rapport d'effectifs en dessous duquel on avertit.

    Les seuils sont des **conventions** : ils sont renvoyés avec les résultats
    pour que l'analyste sache ce qui a déclenché chaque constat.
    """
    _check_unit_interval(confidence_level, "confidence_level")
    _check_positive(outlier_iqr_multiplier, "outlier_iqr_multiplier")
    _check_positive(min_event_count, "min_event_count")
    _check_positive(small_sample, "small_sample")
    _check_positive(skewness_threshold, "skewness_threshold")
    _check_positive(variance_ratio_threshold, "variance_ratio_threshold")
    _check_unit_interval(outlier_rate_threshold, "outlier_rate_threshold")
    _check_unit_interval(balance_threshold, "balance_threshold")

    values_a, values_b = dataset.group_a, dataset.group_b
    balance = Balance(
        n_a=dataset.n_a,
        n_b=dataset.n_b,
        ratio=min(dataset.n_a, dataset.n_b) / max(dataset.n_a, dataset.n_b),
    )

    if dataset.metric_type is MetricType.BINARY:
        group_a = _binary_group(values_a, label="A", level=confidence_level)
        group_b = _binary_group(values_b, label="B", level=confidence_level)
        comparison: BinaryComparison | ContinuousComparison = BinaryComparison(
            absolute_difference=group_b.rate - group_a.rate,
            relative_lift=_ratio(group_b.rate - group_a.rate, group_a.rate),
            risk_ratio=_ratio(group_b.rate, group_a.rate),
            odds_ratio=_odds_ratio(group_a.rate, group_b.rate),
        )
        warnings = _binary_warnings((group_a, group_b), min_event_count=min_event_count)
    else:
        group_a = _continuous_group(
            values_a, label="A", level=confidence_level, iqr_multiplier=outlier_iqr_multiplier
        )
        group_b = _continuous_group(
            values_b, label="B", level=confidence_level, iqr_multiplier=outlier_iqr_multiplier
        )
        variances = (group_a.variance, group_b.variance)
        variance_ratio = _ratio(max(variances), min(variances))
        comparison = ContinuousComparison(
            mean_difference=group_b.mean - group_a.mean,
            median_difference=group_b.median - group_a.median,
            variance_ratio=variance_ratio,
        )
        warnings = _continuous_warnings(
            (group_a, group_b),
            variance_ratio=variance_ratio,
            skewness_threshold=skewness_threshold,
            variance_ratio_threshold=variance_ratio_threshold,
            outlier_rate_threshold=outlier_rate_threshold,
        )

    warnings += _shared_warnings(
        group_a,
        group_b,
        balance,
        small_sample=small_sample,
        balance_threshold=balance_threshold,
    )

    return Diagnostics(
        metric_type=dataset.metric_type,
        unit=dataset.unit,
        group_a=group_a,
        group_b=group_b,
        comparison=comparison,
        balance=balance,
        n_input=dataset.report.n_input,
        n_retained=dataset.report.n_retained,
        n_excluded=dataset.report.n_excluded,
        confidence_level=confidence_level,
        outlier_iqr_multiplier=outlier_iqr_multiplier,
        outlier_rate_threshold=outlier_rate_threshold,
        warnings=tuple(warnings),
    )


def _odds_ratio(rate_a: float, rate_b: float) -> float | None:
    """Rapport des cotes B / A, indéfini si une cote ne l'est pas."""
    odds_a, odds_b = _odds(rate_a), _odds(rate_b)
    if odds_a is None or odds_b is None:
        return None
    return _ratio(odds_b, odds_a)
