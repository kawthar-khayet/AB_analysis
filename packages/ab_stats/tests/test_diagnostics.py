"""Tests des diagnostics (étape 4).

Les valeurs attendues sont calculées à la main sur de petits jeux de données,
ou comparées à une référence indépendante (SciPy, NumPy).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats

from ab_stats.data import GroupMapping, MetricDeclaration, normalize
from ab_stats.diagnostics import (
    BinaryComparison,
    ContinuousComparison,
    diagnose,
)
from ab_stats.exceptions import InvalidParameterError
from ab_stats.results import CIMethod, MetricType, Severity
from ab_stats.simulation import simulate_binary, simulate_continuous

AB = GroupMapping(a="control", b="treatment")
BINARY = MetricDeclaration(MetricType.BINARY)
EUROS = MetricDeclaration(MetricType.CONTINUOUS, unit="euros")

# Jeu de référence continu, calculé à la main dans les tests ci-dessous.
#   A = 1..9 plus une valeur extrême à 30
#   B = 11..20
VALUES_A = [1, 2, 3, 4, 5, 6, 7, 8, 9, 30]
VALUES_B = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]


def build(values_a, values_b, declaration=EUROS):
    groups = ["control"] * len(values_a) + ["treatment"] * len(values_b)
    return normalize(groups, list(values_a) + list(values_b), mapping=AB, declaration=declaration)


def continuous(values_a=VALUES_A, values_b=VALUES_B, **kwargs):
    return diagnose(build(values_a, values_b), **kwargs)


def binary(values_a, values_b, **kwargs):
    return diagnose(build(values_a, values_b, BINARY), **kwargs)


# ---------------------------------------------------------------------------
# Métrique continue : statistiques par groupe
# ---------------------------------------------------------------------------


def test_continuous_group_statistics_match_hand_computed_values() -> None:
    group = continuous().group_a

    assert group.label == "A"
    assert group.n == 10
    assert group.mean == 7.5  # (45 + 30) / 10
    assert group.median == 5.5  # (5 + 6) / 2
    assert group.minimum == 1.0
    assert group.maximum == 30.0
    assert group.q1 == 3.25
    assert group.q3 == 7.75
    assert group.iqr == 4.5
    assert group.variance == pytest.approx(622.5 / 9)  # somme des carrés / (n − 1)
    assert group.standard_deviation == pytest.approx(math.sqrt(622.5 / 9))
    assert group.standard_error == pytest.approx(math.sqrt(622.5 / 9) / math.sqrt(10))


def test_quartiles_match_numpy() -> None:
    group = continuous().group_a
    q1, q3 = np.quantile(VALUES_A, [0.25, 0.75])

    assert (group.q1, group.q3) == (float(q1), float(q3))


def test_skewness_matches_scipy_adjusted_definition() -> None:
    group = continuous().group_a

    assert group.skewness == pytest.approx(float(stats.skew(VALUES_A, bias=False)))
    assert group.skewness > 1  # la valeur à 30 tire une longue traîne à droite


def test_skewness_is_undefined_below_three_observations() -> None:
    assert continuous([1.0, 2.0], [3.0, 5.0]).group_a.skewness is None


def test_symmetric_group_has_skewness_near_zero() -> None:
    assert continuous().group_b.skewness == pytest.approx(0.0, abs=1e-12)


def test_outliers_use_the_declared_quartile_rule() -> None:
    result = continuous()
    group = result.group_a

    assert group.outlier_bounds == (3.25 - 1.5 * 4.5, 7.75 + 1.5 * 4.5)  # (−3.5 ; 14.5)
    assert group.n_outliers == 1  # seulement la valeur 30
    assert group.outlier_rate == 0.1
    assert result.outlier_iqr_multiplier == 1.5
    assert result.group_b.n_outliers == 0


def test_outlier_rule_multiplier_is_configurable() -> None:
    assert continuous(outlier_iqr_multiplier=10.0).group_a.n_outliers == 0


def test_mean_confidence_interval_matches_student_reference() -> None:
    group = continuous().group_a
    half_width = stats.t.ppf(0.975, df=9) * group.standard_error

    assert group.mean_ci.method is CIMethod.STUDENT_T_DIST
    assert group.mean_ci.level == 0.95
    assert group.mean_ci.lower == pytest.approx(7.5 - half_width)
    assert group.mean_ci.upper == pytest.approx(7.5 + half_width)


def test_mean_confidence_interval_is_unavailable_for_a_single_observation() -> None:
    group = continuous([4.0], [1.0, 2.0, 3.0]).group_a

    assert group.n == 1
    assert group.mean_ci.is_available is False
    assert group.standard_deviation == 0.0


# ---------------------------------------------------------------------------
# Métrique continue : comparaison
# ---------------------------------------------------------------------------


def test_continuous_comparison_is_always_b_minus_a() -> None:
    comparison = continuous().comparison

    assert isinstance(comparison, ContinuousComparison)
    assert comparison.mean_difference == pytest.approx(15.5 - 7.5)  # B − A
    assert comparison.median_difference == pytest.approx(15.5 - 5.5)


def test_variance_ratio_puts_the_larger_variance_on_top() -> None:
    comparison = continuous().comparison
    var_a, var_b = 622.5 / 9, np.var(VALUES_B, ddof=1)

    assert comparison.variance_ratio == pytest.approx(max(var_a, var_b) / min(var_a, var_b))
    assert comparison.variance_ratio > 1


def test_variance_ratio_is_undefined_when_a_group_is_constant() -> None:
    assert continuous([5.0] * 5, VALUES_B).comparison.variance_ratio is None


# ---------------------------------------------------------------------------
# Métrique binaire
# ---------------------------------------------------------------------------


def test_binary_group_statistics_match_hand_computed_values() -> None:
    group = binary([0] * 8 + [1] * 2, [1] * 7 + [0] * 3).group_a

    assert (group.n, group.successes, group.failures) == (10, 2, 8)
    assert group.rate == 0.2
    assert group.standard_error == pytest.approx(math.sqrt(0.2 * 0.8 / 10))


def test_binary_rate_interval_is_a_wald_interval_clipped_to_zero_one() -> None:
    group = binary([0] * 8 + [1] * 2, [1] * 7 + [0] * 3).group_a
    half_width = stats.norm.ppf(0.975) * math.sqrt(0.2 * 0.8 / 10)

    assert group.rate_ci.method is CIMethod.WALD
    assert group.rate_ci.upper == pytest.approx(0.2 + half_width)
    assert group.rate_ci.lower == 0.0  # 0,2 − 0,248 serait négatif : borné à 0


def test_binary_comparison_reports_absolute_and_relative_views() -> None:
    comparison = binary([0] * 8 + [1] * 2, [1] * 7 + [0] * 3).comparison

    assert isinstance(comparison, BinaryComparison)
    assert comparison.absolute_difference == pytest.approx(0.5)  # 0,7 − 0,2
    assert comparison.relative_lift == pytest.approx(2.5)  # +250 %
    assert comparison.risk_ratio == pytest.approx(3.5)  # 0,7 / 0,2
    assert comparison.odds_ratio == pytest.approx((0.7 / 0.3) / (0.2 / 0.8))


def test_binary_ratios_are_undefined_when_they_would_divide_by_zero() -> None:
    comparison = binary([0] * 10, [1] * 10).comparison

    assert comparison.absolute_difference == 1.0
    assert comparison.relative_lift is None  # taux de A nul
    assert comparison.risk_ratio is None
    assert comparison.odds_ratio is None  # cote de B indéfinie (taux de B = 1)


# ---------------------------------------------------------------------------
# Effectifs et équilibre
# ---------------------------------------------------------------------------


def test_counts_come_from_the_validation_report() -> None:
    dataset = normalize(
        ["control", "treatment", "control", None, "treatment"],
        [1.0, 2.0, 3.0, 4.0, 5.0],
        mapping=AB,
        declaration=EUROS,
        high_exclusion_rate=0.5,
    )
    result = diagnose(dataset)

    assert (result.n_input, result.n_retained, result.n_excluded) == (5, 4, 1)


def test_balance_ratio_is_symmetric_and_bounded() -> None:
    result = continuous([1.0] * 20 + [2.0], [1.0] * 10)

    assert result.balance.n_a == 21
    assert result.balance.n_b == 10
    assert result.balance.ratio == pytest.approx(10 / 21)


# ---------------------------------------------------------------------------
# Constats
# ---------------------------------------------------------------------------


def clean_binary():
    return simulate_binary(n_a=5_000, n_b=5_000, p_a=0.30, p_b=0.35, seed=7).to_dataset()


def test_clean_binary_dataset_raises_no_warning() -> None:
    assert diagnose(clean_binary()).warnings == ()


def test_clean_normal_dataset_raises_no_warning() -> None:
    dataset = simulate_continuous(
        n_a=2_000, n_b=2_000, mean_a=10.0, mean_b=10.5, std_a=2.0, std_b=2.0, seed=4
    ).to_dataset()

    assert diagnose(dataset).warnings == ()


def test_low_event_count_is_flagged_per_group() -> None:
    result = binary([0] * 95 + [1] * 5, [0] * 50 + [1] * 50)
    warning = next(w for w in result.warnings if w.code == "LOW_EVENT_COUNT")

    assert warning.affected_field == "group_a"
    assert "5 succès" in warning.message
    assert [w.affected_field for w in result.warnings if w.code == "LOW_EVENT_COUNT"] == ["group_a"]


def test_constant_group_is_critical_and_replaces_the_event_count_warning() -> None:
    result = binary([0] * 100, [0] * 50 + [1] * 50)
    warning = next(w for w in result.warnings if w.code == "ZERO_VARIANCE")

    assert warning.severity is Severity.CRITICAL
    assert warning.affected_field == "group_a"
    assert "LOW_EVENT_COUNT" not in result.codes


def test_small_sample_is_flagged_for_both_metric_types() -> None:
    assert "SMALL_SAMPLE" in continuous().codes
    assert "SMALL_SAMPLE" in binary([0, 1] * 5, [0, 1] * 5).codes


def test_high_skewness_is_flagged_on_lognormal_data() -> None:
    dataset = simulate_continuous(
        n_a=2_000,
        n_b=2_000,
        mean_a=50.0,
        mean_b=52.0,
        std_a=60.0,
        std_b=60.0,
        distribution="lognormal",
        seed=3,
    ).to_dataset()

    assert "HIGH_SKEWNESS" in diagnose(dataset).codes


def test_outliers_are_flagged_only_above_the_rate_threshold() -> None:
    dataset = simulate_continuous(
        n_a=2_000,
        n_b=2_000,
        mean_a=10.0,
        mean_b=10.0,
        std_a=2.0,
        std_b=2.0,
        seed=4,
        outlier_rate=0.10,
        outlier_multiplier=8.0,
    ).to_dataset()
    result = diagnose(dataset)

    assert "OUTLIERS_DETECTED" in result.codes
    assert result.group_a.outlier_rate > result.outlier_rate_threshold


def test_unequal_variances_are_flagged_above_the_ratio_threshold() -> None:
    dataset = simulate_continuous(
        n_a=500, n_b=500, mean_a=10.0, mean_b=10.0, std_a=1.0, std_b=5.0, seed=2
    ).to_dataset()

    assert "UNEQUAL_VARIANCES" in diagnose(dataset).codes


def test_similar_variances_are_not_flagged() -> None:
    dataset = simulate_continuous(
        n_a=500, n_b=500, mean_a=10.0, mean_b=10.0, std_a=2.0, std_b=2.2, seed=2
    ).to_dataset()

    assert "UNEQUAL_VARIANCES" not in diagnose(dataset).codes


def test_unbalanced_groups_are_flagged() -> None:
    dataset = simulate_binary(n_a=5_000, n_b=1_000, p_a=0.3, p_b=0.3, seed=1).to_dataset()
    result = diagnose(dataset)

    assert "UNBALANCED_GROUPS" in result.codes
    assert result.balance.ratio == pytest.approx(0.2)


def test_thresholds_are_reported_with_the_results() -> None:
    result = continuous(confidence_level=0.99, outlier_iqr_multiplier=3.0)

    assert result.confidence_level == 0.99
    assert result.outlier_iqr_multiplier == 3.0
    assert result.group_a.mean_ci.level == 0.99


def test_no_warning_mentions_a_statistical_method() -> None:
    """Les constats décrivent les données ; c'est compatibility.py qui conclut."""
    result = continuous()

    assert all(warning.suggested_alternative is None for warning in result.warnings)


# ---------------------------------------------------------------------------
# Paramètres invalides
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("override", "parameter"),
    [
        ({"confidence_level": 0.0}, "confidence_level"),
        ({"confidence_level": 1.0}, "confidence_level"),
        ({"confidence_level": True}, "confidence_level"),
        ({"outlier_iqr_multiplier": 0.0}, "outlier_iqr_multiplier"),
        ({"min_event_count": -1}, "min_event_count"),
        ({"small_sample": 0}, "small_sample"),
        ({"skewness_threshold": 0.0}, "skewness_threshold"),
        ({"variance_ratio_threshold": 0.0}, "variance_ratio_threshold"),
        ({"outlier_rate_threshold": 1.0}, "outlier_rate_threshold"),
        ({"balance_threshold": 0.0}, "balance_threshold"),
    ],
)
def test_invalid_parameters_are_rejected(override, parameter) -> None:
    with pytest.raises(InvalidParameterError) as error:
        continuous(**override)

    assert error.value.code == "INVALID_DIAGNOSTIC_PARAMETER"
    assert error.value.details["parameter"] == parameter
