"""Tests de la simulation reproductible (étape 3)."""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from ab_stats.data import ExclusionReason, NormalizedDataset
from ab_stats.exceptions import InsufficientSampleError, InvalidParameterError
from ab_stats.results import MetricType
from ab_stats.simulation import (
    MAX_SEED,
    ContinuousDistribution,
    simulate_binary,
    simulate_continuous,
)

BINARY = {"n_a": 40, "n_b": 60, "p_a": 0.25, "p_b": 0.40}
CONTINUOUS = {"n_a": 40, "n_b": 60, "mean_a": 10.0, "mean_b": 12.0, "std_a": 2.0, "std_b": 3.0}


def same(first, second) -> bool:
    return (
        first.group == second.group
        and np.array_equal(first.metric, second.metric, equal_nan=True)
        and first.parameters == second.parameters
    )


# ---------------------------------------------------------------------------
# Reproductibilité
# ---------------------------------------------------------------------------


def test_binary_simulation_is_reproducible_with_seed() -> None:
    first = simulate_binary(**BINARY, seed=123, missing_rate=0.1)
    second = simulate_binary(**BINARY, seed=123, missing_rate=0.1)

    assert same(first, second)


def test_continuous_simulation_is_reproducible_with_seed() -> None:
    kwargs = CONTINUOUS | {"seed": 123, "missing_rate": 0.1, "outlier_rate": 0.1}

    assert same(simulate_continuous(**kwargs), simulate_continuous(**kwargs))


def test_different_seeds_give_different_data() -> None:
    first = simulate_continuous(**CONTINUOUS, seed=1)
    second = simulate_continuous(**CONTINUOUS, seed=2)

    assert not np.array_equal(first.metric, second.metric)


def test_missing_seed_is_generated_recorded_and_replayable() -> None:
    original = simulate_continuous(**CONTINUOUS, outlier_rate=0.1, missing_rate=0.1)

    assert original.seed_was_generated
    assert 0 <= original.seed <= MAX_SEED

    replay = simulate_continuous(
        **CONTINUOUS, outlier_rate=0.1, missing_rate=0.1, seed=original.seed
    )
    assert not replay.seed_was_generated
    assert same(original, replay)


def test_binary_draws_match_numpy_reference() -> None:
    result = simulate_binary(n_a=6, n_b=5, p_a=0.3, p_b=0.7, seed=7)

    rng = np.random.default_rng(7)
    expected = np.concatenate([rng.binomial(1, 0.3, size=6), rng.binomial(1, 0.7, size=5)])

    np.testing.assert_array_equal(result.metric, expected)


def test_normal_draws_match_numpy_reference() -> None:
    result = simulate_continuous(
        n_a=4, n_b=3, mean_a=10.0, mean_b=20.0, std_a=2.0, std_b=5.0, seed=7
    )

    rng = np.random.default_rng(7)
    expected = np.concatenate(
        [rng.normal(10.0, 2.0, size=4), rng.normal(20.0, 5.0, size=3)]
    )

    np.testing.assert_array_equal(result.metric, expected)


# ---------------------------------------------------------------------------
# Forme des colonnes
# ---------------------------------------------------------------------------


def test_columns_have_the_requested_group_sizes() -> None:
    result = simulate_binary(n_a=11, n_b=17, p_a=0.2, p_b=0.8, seed=42)

    assert result.group == ("A",) * 11 + ("B",) * 17
    assert result.metric.shape == (28,)
    assert result.metric_type is MetricType.BINARY


def test_simulated_columns_and_parameters_are_immutable() -> None:
    result = simulate_binary(**BINARY, seed=1)

    with pytest.raises(ValueError):
        result.metric[0] = 5.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.parameters.p_a = 0.9


def test_degenerate_probabilities_are_allowed() -> None:
    result = simulate_binary(n_a=50, n_b=50, p_a=0.0, p_b=1.0, seed=3)

    assert np.all(result.metric[:50] == 0)
    assert np.all(result.metric[50:] == 1)


# ---------------------------------------------------------------------------
# Fidélité aux paramètres
# ---------------------------------------------------------------------------


def test_binary_empirical_rates_are_close_to_parameters() -> None:
    dataset = simulate_binary(n_a=20_000, n_b=20_000, p_a=0.25, p_b=0.65, seed=2026).to_dataset()

    assert math.isclose(dataset.group_a.mean(), 0.25, abs_tol=0.02)
    assert math.isclose(dataset.group_b.mean(), 0.65, abs_tol=0.02)


@pytest.mark.parametrize("distribution", list(ContinuousDistribution))
def test_continuous_empirical_moments_are_close_to_parameters(distribution) -> None:
    dataset = simulate_continuous(
        n_a=50_000,
        n_b=50_000,
        mean_a=10.0,
        mean_b=12.0,
        std_a=2.0,
        std_b=3.0,
        distribution=distribution,
        seed=2026,
    ).to_dataset()

    assert math.isclose(dataset.group_a.mean(), 10.0, abs_tol=0.15)
    assert math.isclose(dataset.group_b.mean(), 12.0, abs_tol=0.20)
    assert math.isclose(dataset.group_a.std(), 2.0, abs_tol=0.15)
    assert math.isclose(dataset.group_b.std(), 3.0, abs_tol=0.20)


def test_lognormal_is_right_skewed_and_normal_is_not() -> None:
    def skewness(values: np.ndarray) -> float:
        centered = values - values.mean()
        return float((centered**3).mean() / values.std() ** 3)

    common = CONTINUOUS | {"n_a": 20_000, "n_b": 20_000, "seed": 5}
    normal = simulate_continuous(**common).to_dataset()
    lognormal = simulate_continuous(**common, distribution="lognormal").to_dataset()

    assert abs(skewness(normal.group_a)) < 0.1
    assert skewness(lognormal.group_a) > 0.3


# ---------------------------------------------------------------------------
# Contaminations
# ---------------------------------------------------------------------------


def test_missing_values_are_counted_per_group() -> None:
    result = simulate_binary(n_a=100, n_b=120, p_a=0.5, p_b=0.5, seed=99, missing_rate=0.2)

    assert result.missing_count_a == int(np.isnan(result.metric[:100]).sum()) > 0
    assert result.missing_count_b == int(np.isnan(result.metric[100:]).sum()) > 0


def test_outliers_shift_values_by_exactly_the_multiplier() -> None:
    kwargs = {"n_a": 30, "n_b": 30, "mean_a": 0.0, "mean_b": 0.0, "std_a": 1.0, "std_b": 2.0}
    baseline = simulate_continuous(**kwargs, seed=42)
    shifted = simulate_continuous(**kwargs, seed=42, outlier_rate=1.0, outlier_multiplier=10.0)

    assert shifted.outlier_count_a == 30
    assert shifted.outlier_count_b == 30
    np.testing.assert_allclose(np.abs(shifted.metric[:30] - baseline.metric[:30]), 10.0)
    np.testing.assert_allclose(np.abs(shifted.metric[30:] - baseline.metric[30:]), 20.0)


# ---------------------------------------------------------------------------
# Passage par le pipeline d'import
# ---------------------------------------------------------------------------


def test_simulation_normalizes_like_a_csv_import() -> None:
    result = simulate_continuous(**CONTINUOUS, seed=8, unit="euros")
    dataset = result.to_dataset()

    assert isinstance(dataset, NormalizedDataset)
    assert dataset.metric_type is MetricType.CONTINUOUS
    assert dataset.unit == "euros"
    assert (dataset.n_a, dataset.n_b) == (40, 60)
    assert dataset.report.n_excluded == 0


def test_binary_simulation_uses_proportion_unit() -> None:
    assert simulate_binary(**BINARY, seed=8).to_dataset().unit == "proportion"


def test_simulated_missing_values_are_excluded_and_reported() -> None:
    result = simulate_binary(n_a=200, n_b=200, p_a=0.3, p_b=0.4, seed=11, missing_rate=0.15)
    dataset = result.to_dataset(high_exclusion_rate=0.5)

    missing = result.missing_count_a + result.missing_count_b
    assert dataset.report.excluded(ExclusionReason.MISSING_METRIC) == missing
    assert dataset.n_a == 200 - result.missing_count_a
    assert dataset.n_b == 200 - result.missing_count_b


def test_simulation_that_empties_a_group_fails_only_at_normalization() -> None:
    result = simulate_binary(**BINARY, seed=1, missing_rate=1.0)

    assert result.missing_count_a == 40
    with pytest.raises(InsufficientSampleError) as error:
        result.to_dataset()
    assert error.value.code == "ALL_ROWS_EXCLUDED"


# ---------------------------------------------------------------------------
# Paramètres invalides
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("override", "parameter"),
    [
        ({"n_a": 0}, "n_a"),
        ({"n_b": 2.5}, "n_b"),
        ({"n_a": True}, "n_a"),
        ({"p_a": -0.1}, "p_a"),
        ({"p_b": 1.1}, "p_b"),
        ({"p_b": math.nan}, "p_b"),
        ({"missing_rate": 1.01}, "missing_rate"),
        ({"seed": -1}, "seed"),
        ({"seed": MAX_SEED + 1}, "seed"),
        ({"seed": True}, "seed"),
        ({"seed": 3.0}, "seed"),
    ],
)
def test_binary_simulation_rejects_invalid_parameters(override, parameter) -> None:
    with pytest.raises(InvalidParameterError) as error:
        simulate_binary(**(BINARY | override))

    assert error.value.code == "INVALID_SIMULATION_PARAMETER"
    assert error.value.details["parameter"] == parameter


@pytest.mark.parametrize(
    ("override", "parameter"),
    [
        ({"mean_a": math.inf}, "mean_a"),
        ({"mean_b": math.nan}, "mean_b"),
        ({"std_a": 0.0}, "std_a"),
        ({"std_b": -1.0}, "std_b"),
        ({"outlier_rate": -0.01}, "outlier_rate"),
        ({"outlier_multiplier": 0.0}, "outlier_multiplier"),
        ({"distribution": "gamma"}, "distribution"),
        ({"distribution": "lognormal", "mean_a": 0.0}, "mean_a"),
        ({"unit": "  "}, "unit"),
    ],
)
def test_continuous_simulation_rejects_invalid_parameters(override, parameter) -> None:
    with pytest.raises(InvalidParameterError) as error:
        simulate_continuous(**(CONTINUOUS | override))

    assert error.value.details["parameter"] == parameter
