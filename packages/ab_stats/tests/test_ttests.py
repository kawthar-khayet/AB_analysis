"""Tests du test t de Welch (étape 7)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from ab_stats.analyses.continuous import welch_t
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



def test_welch_t_warns_on_skewed_data_and_suggests_bootstrap() -> None:
    rng = np.random.default_rng(7)
    a = rng.lognormal(3.0, 1.0, 200)
    b = rng.lognormal(3.1, 1.0, 200)
    res = welch_t(a, b)
    skew = [w for w in res.warnings if w.code == "HIGH_SKEWNESS"]
    assert skew and skew[0].suggested_alternative == Method.BOOTSTRAP


def test_welch_t_df_is_between_min_group_and_pooled_df() -> None:
    rng = np.random.default_rng(3)
    a = rng.normal(0.0, 1.0, 40)
    b = rng.normal(0.0, 5.0, 25)
    res = welch_t(a, b)
    assert 24 <= res.statistic.df <= 40 + 25 - 2
