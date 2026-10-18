"""Tests des tests t de Welch et Student (étape 7)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from ab_stats.analyses.continuous import student_t, welch_t
from ab_stats.results import (
    Alternative,
    CIMethod,
    Decision,
    Method,
    MetricType,
    PValueSource,
)


def test_welch_t_against_scipy() -> None:
    rng = np.random.default_rng(12345)
    a = rng.normal(loc=10.0, scale=2.0, size=100)
    b = rng.normal(loc=11.0, scale=3.0, size=80)

    res = welch_t(a, b, alpha=0.05, alternative=Alternative.TWO_SIDED)

    ref = stats.ttest_ind(b, a, equal_var=False)

    assert res.method == Method.WELCH_T
    assert res.metric_type == MetricType.CONTINUOUS
    assert pytest.approx(res.statistic.value) == ref.statistic
    assert pytest.approx(res.p_value) == ref.pvalue
    assert res.p_value_source == PValueSource.ANALYTIC
    assert res.confidence_interval.method == CIMethod.WELCH_T_DIST
    assert res.decision == (Decision.REJECT_NULL if ref.pvalue <= 0.05 else Decision.FAIL_TO_REJECT_NULL)


def test_student_t_against_scipy() -> None:
    rng = np.random.default_rng(54321)
    a = rng.normal(loc=50.0, scale=5.0, size=60)
    b = rng.normal(loc=53.0, scale=5.0, size=60)

    res = student_t(a, b, alpha=0.05, alternative=Alternative.GREATER)

    ref = stats.ttest_ind(b, a, equal_var=True, alternative="greater")

    assert res.method == Method.STUDENT_T
    assert pytest.approx(res.statistic.value) == ref.statistic
    assert pytest.approx(res.p_value) == ref.pvalue
    assert res.confidence_interval.method == CIMethod.STUDENT_T_DIST
    assert res.statistic.df == 118


def test_student_t_warning_on_unequal_variances() -> None:
    a = [10.0, 10.1, 9.9, 10.0, 10.2]
    b = [5.0, 15.0, 25.0, -5.0, 30.0]  # Variance beaucoup plus forte
    res = student_t(a, b)
    assert any(w.code == "UNEQUAL_VARIANCES" for w in res.warnings)
