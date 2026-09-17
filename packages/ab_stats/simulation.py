"""Simulation reproductible d'expériences A/B.

Trois usages :

* tester tout le pipeline sans fichier CSV, sur des données dont on connaît la
  vérité (« j'ai mis un vrai écart de 2 points ») ;
* alimenter les vérifications Monte-Carlo de l'étape 10 ;
* offrir à l'utilisateur une expérience à explorer (``POST /simulations``).

Une simulation produit **les mêmes deux colonnes qu'un import CSV** — une
colonne groupe (``"A"`` / ``"B"``) et une colonne métrique — et passe ensuite par
:func:`ab_stats.data.normalize`, exactement comme un fichier importé. Les valeurs
manquantes simulées sont donc écartées et comptées par le même code, et les
modules en aval ne savent pas, et n'ont pas à savoir, d'où viennent les données.

Reproductibilité : une graine détermine entièrement le résultat. Si aucune graine
n'est fournie, une graine est tirée **et enregistrée**, de sorte que toute
simulation puisse être rejouée à l'identique après coup.

Mécanique de tirage inspirée du simulateur d'ExperimentOS (même ordre de
tirage : échantillon A, échantillon B, puis contaminations).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from ab_stats.data import (
    DEFAULT_HIGH_EXCLUSION_RATE,
    GroupMapping,
    MetricDeclaration,
    NormalizedDataset,
    normalize,
)
from ab_stats.exceptions import InvalidParameterError
from ab_stats.results import MetricType

__all__ = [
    "SIMULATION_MAPPING",
    "MAX_SEED",
    "DEFAULT_CONTINUOUS_UNIT",
    "ContinuousDistribution",
    "BinarySimulationParameters",
    "ContinuousSimulationParameters",
    "SimulatedExperiment",
    "simulate_binary",
    "simulate_continuous",
]


#: Étiquettes de la colonne groupe d'une simulation.
SIMULATION_MAPPING = GroupMapping(a="A", b="B")

#: Plus grande graine acceptée. Au-delà de 2**53 − 1, un nombre entier perd sa
#: précision en JavaScript : le frontend, qui conserve la graine, ne pourrait
#: plus rejouer la simulation à l'identique.
MAX_SEED = 2**53 - 1

#: Unité par défaut d'une métrique continue simulée.
DEFAULT_CONTINUOUS_UNIT = "units"


class ContinuousDistribution(str, Enum):
    """Forme de la distribution d'une métrique continue simulée.

    Les trois formes sont paramétrées par la même moyenne et le même écart-type
    cibles, ce qui permet de comparer des tests sur des données de même
    ampleur mais de forme différente.
    """

    NORMAL = "normal"
    """Symétrique : le cas où les t-tests sont dans leur élément."""

    EXPONENTIAL = "exponential"
    """Asymétrique, décalée pour atteindre la moyenne cible."""

    LOGNORMAL = "lognormal"
    """Fortement asymétrique et positive, comme un montant de panier."""


# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BinarySimulationParameters:
    """Paramètres complets d'une simulation binaire, graine comprise."""

    n_a: int
    n_b: int
    p_a: float
    p_b: float
    seed: int
    missing_rate: float


@dataclass(frozen=True, slots=True)
class ContinuousSimulationParameters:
    """Paramètres complets d'une simulation continue, graine comprise."""

    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    std_a: float
    std_b: float
    distribution: ContinuousDistribution
    seed: int
    missing_rate: float
    outlier_rate: float
    outlier_multiplier: float
    unit: str


# ---------------------------------------------------------------------------
# Résultat
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, eq=False)
class SimulatedExperiment:
    """Une expérience simulée, sous la forme de deux colonnes brutes.

    Les lignes du groupe A précèdent celles du groupe B. Une valeur manquante
    de la métrique vaut ``NaN``.
    """

    group: tuple[str, ...]
    metric: np.ndarray
    metric_type: MetricType
    parameters: BinarySimulationParameters | ContinuousSimulationParameters
    seed_was_generated: bool
    missing_count_a: int
    missing_count_b: int
    outlier_count_a: int = 0
    outlier_count_b: int = 0

    @property
    def seed(self) -> int:
        """Graine qui permet de rejouer exactement cette simulation."""
        return self.parameters.seed

    @property
    def declaration(self) -> MetricDeclaration:
        """Déclaration de métrique correspondant à la simulation."""
        if self.metric_type is MetricType.BINARY:
            return MetricDeclaration(MetricType.BINARY)
        return MetricDeclaration(MetricType.CONTINUOUS, unit=self.parameters.unit)

    def to_dataset(
        self,
        *,
        high_exclusion_rate: float = DEFAULT_HIGH_EXCLUSION_RATE,
    ) -> NormalizedDataset:
        """Normalise la simulation comme un import CSV.

        Raises:
            InsufficientSampleError: si les valeurs manquantes simulées vident
                un groupe (par exemple ``missing_rate=1``).
        """
        return normalize(
            self.group,
            self.metric,
            mapping=SIMULATION_MAPPING,
            declaration=self.declaration,
            high_exclusion_rate=high_exclusion_rate,
        )


# ---------------------------------------------------------------------------
# Validation des paramètres
# ---------------------------------------------------------------------------


def _invalid(parameter: str, value: Any, message: str) -> InvalidParameterError:
    return InvalidParameterError(
        "INVALID_SIMULATION_PARAMETER",
        message,
        details={"parameter": parameter, "value": value},
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_size(value: Any, parameter: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _invalid(parameter, value, "Un effectif doit être un entier supérieur ou égal à 1.")


def _check_finite(value: Any, parameter: str) -> None:
    if not _is_number(value) or not math.isfinite(value):
        raise _invalid(parameter, value, "Ce paramètre doit être un nombre fini.")


def _check_positive(value: Any, parameter: str) -> None:
    _check_finite(value, parameter)
    if value <= 0:
        raise _invalid(parameter, value, "Ce paramètre doit être strictement positif.")


def _check_probability(value: Any, parameter: str) -> None:
    if not _is_number(value) or not 0.0 <= value <= 1.0:
        raise _invalid(parameter, value, "Une probabilité doit être comprise entre 0 et 1.")


def _resolve_seed(seed: Any) -> tuple[int, bool]:
    """Graine à utiliser, et indique si elle a dû être tirée."""
    if seed is None:
        generated = int(np.random.SeedSequence().generate_state(1, dtype=np.uint32)[0])
        return generated, True
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise _invalid("seed", seed, "La graine doit être un entier.")
    if not 0 <= int(seed) <= MAX_SEED:
        raise _invalid("seed", seed, f"La graine doit être comprise entre 0 et {MAX_SEED}.")
    return int(seed), False


def _resolve_distribution(distribution: Any) -> ContinuousDistribution:
    try:
        return ContinuousDistribution(distribution)
    except ValueError as error:
        raise _invalid(
            "distribution",
            str(distribution),
            "Distribution non prise en charge (normal, exponential, lognormal).",
        ) from error


# ---------------------------------------------------------------------------
# Tirages
# ---------------------------------------------------------------------------


def _draw_continuous(
    *,
    n: int,
    mean: float,
    std: float,
    distribution: ContinuousDistribution,
    rng: np.random.Generator,
) -> np.ndarray:
    """Tire un échantillon continu de moyenne et d'écart-type cibles."""
    if distribution is ContinuousDistribution.NORMAL:
        return rng.normal(loc=mean, scale=std, size=n)
    if distribution is ContinuousDistribution.EXPONENTIAL:
        # Une loi exponentielle d'échelle σ a pour moyenne et écart-type σ :
        # on la décale pour atteindre la moyenne cible.
        return rng.exponential(scale=std, size=n) + mean - std
    # Paramètres de la loi normale sous-jacente d'une log-normale de moyenne et
    # d'écart-type donnés.
    sigma = math.sqrt(math.log1p((std / mean) ** 2))
    mu = math.log(mean) - sigma**2 / 2
    return rng.lognormal(mean=mu, sigma=sigma, size=n)


def _add_outliers(
    values: np.ndarray,
    *,
    std: float,
    rate: float,
    multiplier: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int]:
    """Décale une part des observations de ± ``multiplier`` écarts-types."""
    contaminated = values.astype(np.float64, copy=True)
    if rate == 0:
        return contaminated, 0
    mask = rng.random(contaminated.size) < rate
    count = int(mask.sum())
    signs = rng.choice(np.array([-1.0, 1.0]), size=count)
    contaminated[mask] += signs * multiplier * std
    return contaminated, count


def _add_missing(
    values: np.ndarray,
    *,
    rate: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int]:
    """Remplace une part des observations par ``NaN``."""
    contaminated = values.astype(np.float64, copy=True)
    if rate == 0:
        return contaminated, 0
    mask = rng.random(contaminated.size) < rate
    contaminated[mask] = np.nan
    return contaminated, int(mask.sum())


def _columns(group_a: np.ndarray, group_b: np.ndarray) -> tuple[tuple[str, ...], np.ndarray]:
    """Assemble les deux échantillons en colonnes groupe et métrique."""
    group = (SIMULATION_MAPPING.a,) * group_a.size + (SIMULATION_MAPPING.b,) * group_b.size
    metric = np.concatenate([group_a, group_b])
    metric.setflags(write=False)
    return group, metric


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def simulate_binary(
    *,
    n_a: int,
    n_b: int,
    p_a: float,
    p_b: float,
    seed: int | None = None,
    missing_rate: float = 0.0,
) -> SimulatedExperiment:
    """Simule une expérience binaire : chaque participant convertit ou non.

    Args:
        n_a, n_b: effectifs des groupes A et B.
        p_a, p_b: taux de conversion réels des groupes A et B.
        seed: graine ; tirée et enregistrée si absente.
        missing_rate: part des métriques remplacées par une valeur manquante.
    """
    _check_size(n_a, "n_a")
    _check_size(n_b, "n_b")
    _check_probability(p_a, "p_a")
    _check_probability(p_b, "p_b")
    _check_probability(missing_rate, "missing_rate")
    resolved_seed, generated = _resolve_seed(seed)

    rng = np.random.default_rng(resolved_seed)
    raw_a = rng.binomial(1, p_a, size=n_a)
    raw_b = rng.binomial(1, p_b, size=n_b)
    group_a, missing_a = _add_missing(raw_a, rate=missing_rate, rng=rng)
    group_b, missing_b = _add_missing(raw_b, rate=missing_rate, rng=rng)
    group, metric = _columns(group_a, group_b)

    return SimulatedExperiment(
        group=group,
        metric=metric,
        metric_type=MetricType.BINARY,
        parameters=BinarySimulationParameters(
            n_a=n_a,
            n_b=n_b,
            p_a=float(p_a),
            p_b=float(p_b),
            seed=resolved_seed,
            missing_rate=float(missing_rate),
        ),
        seed_was_generated=generated,
        missing_count_a=missing_a,
        missing_count_b=missing_b,
    )


def simulate_continuous(
    *,
    n_a: int,
    n_b: int,
    mean_a: float,
    mean_b: float,
    std_a: float,
    std_b: float,
    distribution: ContinuousDistribution | str = ContinuousDistribution.NORMAL,
    seed: int | None = None,
    missing_rate: float = 0.0,
    outlier_rate: float = 0.0,
    outlier_multiplier: float = 6.0,
    unit: str = DEFAULT_CONTINUOUS_UNIT,
) -> SimulatedExperiment:
    """Simule une expérience continue : chaque participant produit une mesure.

    Args:
        n_a, n_b: effectifs des groupes A et B.
        mean_a, mean_b: moyennes réelles des groupes A et B.
        std_a, std_b: écarts-types réels des groupes A et B.
        distribution: forme de la distribution.
        seed: graine ; tirée et enregistrée si absente.
        missing_rate: part des métriques remplacées par une valeur manquante.
        outlier_rate: part des métriques décalées en valeurs extrêmes.
        outlier_multiplier: amplitude du décalage, en écarts-types.
        unit: unité de la métrique.
    """
    _check_size(n_a, "n_a")
    _check_size(n_b, "n_b")
    _check_finite(mean_a, "mean_a")
    _check_finite(mean_b, "mean_b")
    _check_positive(std_a, "std_a")
    _check_positive(std_b, "std_b")
    _check_probability(missing_rate, "missing_rate")
    _check_probability(outlier_rate, "outlier_rate")
    _check_positive(outlier_multiplier, "outlier_multiplier")
    resolved_distribution = _resolve_distribution(distribution)
    if resolved_distribution is ContinuousDistribution.LOGNORMAL:
        for parameter, mean in (("mean_a", mean_a), ("mean_b", mean_b)):
            if mean <= 0:
                raise _invalid(
                    parameter, mean, "Une distribution log-normale exige une moyenne positive."
                )
    if not isinstance(unit, str) or not unit.strip():
        raise _invalid("unit", unit, "L'unité d'une métrique continue est obligatoire.")
    resolved_seed, generated = _resolve_seed(seed)

    rng = np.random.default_rng(resolved_seed)
    raw_a = _draw_continuous(
        n=n_a, mean=mean_a, std=std_a, distribution=resolved_distribution, rng=rng
    )
    raw_b = _draw_continuous(
        n=n_b, mean=mean_b, std=std_b, distribution=resolved_distribution, rng=rng
    )
    shifted_a, outliers_a = _add_outliers(
        raw_a, std=std_a, rate=outlier_rate, multiplier=outlier_multiplier, rng=rng
    )
    shifted_b, outliers_b = _add_outliers(
        raw_b, std=std_b, rate=outlier_rate, multiplier=outlier_multiplier, rng=rng
    )
    group_a, missing_a = _add_missing(shifted_a, rate=missing_rate, rng=rng)
    group_b, missing_b = _add_missing(shifted_b, rate=missing_rate, rng=rng)
    group, metric = _columns(group_a, group_b)

    return SimulatedExperiment(
        group=group,
        metric=metric,
        metric_type=MetricType.CONTINUOUS,
        parameters=ContinuousSimulationParameters(
            n_a=n_a,
            n_b=n_b,
            mean_a=float(mean_a),
            mean_b=float(mean_b),
            std_a=float(std_a),
            std_b=float(std_b),
            distribution=resolved_distribution,
            seed=resolved_seed,
            missing_rate=float(missing_rate),
            outlier_rate=float(outlier_rate),
            outlier_multiplier=float(outlier_multiplier),
            unit=unit,
        ),
        seed_was_generated=generated,
        missing_count_a=missing_a,
        missing_count_b=missing_b,
        outlier_count_a=outliers_a,
        outlier_count_b=outliers_b,
    )
