"""Tests de Mann-Whitney U (étape 18)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from ab_stats.analyses.nonparametric import mann_whitney_u
from ab_stats.results import (
    CIMethod,
    Decision,
    EffectSizeName,
    EstimateName,
    Method,
)


def test_mann_whitney_u_basic() -> None:
    rng = np.random.default_rng(42)
    a = rng.exponential(scale=2.0, size=50)
    b = rng.exponential(scale=4.0, size=50)

    res = mann_whitney_u(a, b, alpha=0.05)

    ref = stats.mannwhitneyu(b, a, alternative="two-sided")

    assert res.method == Method.MANN_WHITNEY_U
    assert pytest.approx(res.statistic.value) == ref.statistic
    assert pytest.approx(res.p_value) == ref.pvalue
    assert res.estimate.name == EstimateName.HODGES_LEHMANN
    assert res.confidence_interval.method == CIMethod.HODGES_LEHMANN
    assert res.effect_size.name == EffectSizeName.CLIFFS_DELTA
    assert res.decision == Decision.REJECT_NULL


def test_mann_whitney_ties_warning() -> None:
    a = [1, 2, 2, 3, 4]
    b = [2, 3, 3, 4, 5]
    res = mann_whitney_u(a, b)
    assert any(w.code == "TIES_PRESENT" for w in res.warnings)
