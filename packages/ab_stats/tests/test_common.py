"""Tests des briques partagées par les méthodes (étape N1)."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest

from ab_stats.analyses._common import (
    MAX_RESAMPLES,
    MIN_RESAMPLES,
    TRACKED_LIBRARIES,
    build_reproducibility,
    compute_input_hash,
    library_versions,
    normalize_alternative,
    to_scipy_alternative,
    to_statsmodels_alternative,
    validate_alpha,
    validate_confidence_level,
    validate_n_resamples,
    validate_seed,
)
from ab_stats.exceptions import InvalidParameterError
from ab_stats.results import Alternative

# ---------------------------------------------------------------------------
# Validation des paramètres
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("validator", [validate_alpha, validate_confidence_level])
@pytest.mark.parametrize("value", [0.0, 1.0, -0.5, 1.5, "0.05", True, None])
def test_unit_interval_parameters_reject_invalid_values(validator, value) -> None:
    with pytest.raises(InvalidParameterError) as error:
        validator(value)

    assert error.value.code == "INVALID_ANALYSIS_PARAMETER"


@pytest.mark.parametrize("validator", [validate_alpha, validate_confidence_level])
def test_unit_interval_parameters_accept_valid_values(validator) -> None:
    validator(0.05)
    validator(0.95)


def test_seed_is_mandatory() -> None:
    with pytest.raises(InvalidParameterError, match="obligatoire"):
        validate_seed(None)  # type: ignore[arg-type]


@pytest.mark.parametrize("seed", [-1, 1.5, "42", True])
def test_seed_must_be_a_non_negative_integer(seed) -> None:
    with pytest.raises(InvalidParameterError):
        validate_seed(seed)


def test_seed_accepts_zero_and_positive_integers() -> None:
    validate_seed(0)
    validate_seed(20261006)


@pytest.mark.parametrize("n", [MIN_RESAMPLES - 1, MAX_RESAMPLES + 1, 1000.0, True])
def test_n_resamples_rejects_out_of_range_values(n) -> None:
    with pytest.raises(InvalidParameterError) as error:
        validate_n_resamples(n)

    assert error.value.details["minimum"] == MIN_RESAMPLES


@pytest.mark.parametrize("n", [MIN_RESAMPLES, 10_000, MAX_RESAMPLES])
def test_n_resamples_accepts_bounds(n: int) -> None:
    validate_n_resamples(n)


# ---------------------------------------------------------------------------
# Traduction de l'alternative
# ---------------------------------------------------------------------------


def test_alternative_accepts_enum_and_text() -> None:
    assert normalize_alternative("greater") is Alternative.GREATER
    assert normalize_alternative(Alternative.LESS) is Alternative.LESS


def test_unknown_alternative_is_refused() -> None:
    with pytest.raises(InvalidParameterError) as error:
        normalize_alternative("larger")

    assert error.value.details["allowed"] == ["two_sided", "greater", "less"]


@pytest.mark.parametrize(
    ("alternative", "scipy_name", "statsmodels_name"),
    [
        (Alternative.TWO_SIDED, "two-sided", "two-sided"),
        (Alternative.GREATER, "greater", "larger"),
        (Alternative.LESS, "less", "smaller"),
    ],
)
def test_alternative_vocabularies(alternative, scipy_name, statsmodels_name) -> None:
    assert to_scipy_alternative(alternative) == scipy_name
    assert to_statsmodels_alternative(alternative) == statsmodels_name


def test_greater_means_b_above_a_in_statsmodels() -> None:
    # Scénario du rapport : B (12,4 %) fait mieux que A (11,1 %).
    # B passé en premier : « greater » doit donner une p-value minuscule.
    _, p_greater = proportions_ztest(
        [6_200, 5_550], [50_000, 50_000], alternative=to_statsmodels_alternative("greater")
    )
    _, p_less = proportions_ztest(
        [6_200, 5_550], [50_000, 50_000], alternative=to_statsmodels_alternative("less")
    )

    assert p_greater < 1e-9
    assert p_less > 0.99


def test_greater_means_b_above_a_in_scipy() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    b = a + 10.0

    p_greater = stats.ttest_ind(b, a, alternative=to_scipy_alternative("greater")).pvalue

    assert p_greater < 1e-5


# ---------------------------------------------------------------------------
# Reproductibilité
# ---------------------------------------------------------------------------


def test_input_hash_is_deterministic_and_declares_its_algorithm() -> None:
    first = compute_input_hash([1, 0, 1], [0, 0, 1])

    assert first == compute_input_hash(np.array([1.0, 0.0, 1.0]), (0, 0, 1))
    assert first.startswith("sha256:")


def test_input_hash_depends_on_group_boundaries() -> None:
    assert compute_input_hash([1, 2], [3]) != compute_input_hash([1], [2, 3])


def test_input_hash_depends_on_group_order() -> None:
    assert compute_input_hash([1, 2], [3, 4]) != compute_input_hash([3, 4], [1, 2])


def test_input_hash_depends_on_values() -> None:
    assert compute_input_hash([1, 2], [3, 4]) != compute_input_hash([1, 2], [3, 5])


def test_input_hash_treats_negative_zero_as_zero() -> None:
    assert compute_input_hash([-0.0], [1.0]) == compute_input_hash([0.0], [1.0])


def test_library_versions_track_the_computation_stack() -> None:
    versions = library_versions()

    assert set(versions) == set(TRACKED_LIBRARIES)
    assert versions["statsmodels"] != "non installé"


def test_build_reproducibility() -> None:
    moment = datetime(2026, 10, 6, tzinfo=timezone.utc)

    built = build_reproducibility([1, 0], [0, 1], seed=7, n_resamples=1_000, computed_at=moment)

    assert built.computed_at == moment
    assert built.input_hash == compute_input_hash([1, 0], [0, 1])
    assert built.seed == 7
    assert built.n_resamples == 1_000
    assert "numpy" in built.versions


def test_build_reproducibility_defaults_to_now_in_utc() -> None:
    built = build_reproducibility([1.0], [2.0])

    assert built.computed_at.tzinfo is timezone.utc
    assert built.seed is None
