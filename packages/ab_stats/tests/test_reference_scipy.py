"""Tests de référence contre SciPy et Statsmodels + vérification Monte-Carlo A/A (étape 10)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest

from ab_stats.analyses import (
    bootstrap_test,
    fisher_exact,
    mann_whitney_u,
    permutation_test,
    student_t,
    two_proportion_z,
    welch_t,
)
from ab_stats.results import Alternative


def test_reference_proportions_ztest() -> None:
    # Comparaison exacte avec statsmodels
    succ_a, n_a = 55, 500
    succ_b, n_b = 75, 500

    a = [1] * succ_a + [0] * (n_a - succ_a)
    b = [1] * succ_b + [0] * (n_b - succ_b)

    res = two_proportion_z(a, b)

    # Statsmodels proportions_ztest compare count1/nobs1 à count2/nobs2 : B vs A
    sm_z, sm_p = proportions_ztest([succ_b, succ_a], [n_b, n_a], alternative="two-sided")

    assert pytest.approx(res.statistic.value, abs=1e-5) == sm_z
    assert pytest.approx(res.p_value, abs=1e-5) == sm_p


def test_reference_scipy_fisher() -> None:
    table_b_a = [[14, 20], [8, 25]]  # B row, A row
    b = [1] * 14 + [0] * 20
    a = [1] * 8 + [0] * 25

    res = fisher_exact(a, b)
    ref = stats.fisher_exact(table_b_a, alternative="two-sided")

    assert pytest.approx(res.statistic.value, abs=1e-5) == ref.statistic
    assert pytest.approx(res.p_value, abs=1e-5) == ref.pvalue


def test_reference_scipy_welch_and_student() -> None:
    rng = np.random.default_rng(777)
    a = rng.normal(5.0, 1.2, 80)
    b = rng.normal(5.5, 1.8, 70)

    res_w = welch_t(a, b)
    ref_w = stats.ttest_ind(b, a, equal_var=False)
    assert pytest.approx(res_w.statistic.value, abs=1e-5) == ref_w.statistic
    assert pytest.approx(res_w.p_value, abs=1e-5) == ref_w.pvalue

    res_s = student_t(a, b)
    ref_s = stats.ttest_ind(b, a, equal_var=True)
    assert pytest.approx(res_s.statistic.value, abs=1e-5) == ref_s.statistic
    assert pytest.approx(res_s.p_value, abs=1e-5) == ref_s.pvalue


def test_reference_scipy_mann_whitney() -> None:
    rng = np.random.default_rng(888)
    a = rng.lognormal(0.0, 0.5, 60)
    b = rng.lognormal(0.3, 0.5, 60)

    res = mann_whitney_u(a, b)
    ref = stats.mannwhitneyu(b, a, alternative="two-sided")
    assert pytest.approx(res.statistic.value, abs=1e-5) == ref.statistic
    assert pytest.approx(res.p_value, abs=1e-5) == ref.pvalue


def test_monte_carlo_aa_null_rejection_rate() -> None:
    """Test A/A : sous H0, le taux de rejet au seuil alpha=0.05 doit être proche de 5%."""
    rng = np.random.default_rng(42)
    n_simulations = 400
    alpha = 0.05

    rejections = 0
    for _ in range(n_simulations):
        # Tirage sous H0 (même loi normale N(10, 2))
        a = rng.normal(10.0, 2.0, 60)
        b = rng.normal(10.0, 2.0, 60)
        res = welch_t(a, b, alpha=alpha)
        if res.is_significant:
            rejections += 1

    rejection_rate = rejections / n_simulations
    # Intervalle binomial 95% pour n=400, p=0.05 : [0.03, 0.075] environ
    assert 0.02 <= rejection_rate <= 0.09
