"""Tests des analyses de proportions (étape 6 & 18)."""

from __future__ import annotations

import numpy as np
import pytest

from ab_stats.analyses.binary import fisher_exact, two_proportion_z
from ab_stats.results import (
    Alternative,
    CIMethod,
    Decision,
    EffectSizeName,
    EstimateName,
    Method,
    MetricType,
    PValueSource,
)


def test_two_proportion_z_report_reference_scenario() -> None:
    # 5 550 / 50 000 (0.111) contre 6 200 / 50 000 (0.124)
    a = np.zeros(50_000, dtype=int)
    a[:5_550] = 1
    b = np.zeros(50_000, dtype=int)
    b[:6_200] = 1

    res = two_proportion_z(a, b, alpha=0.05, alternative=Alternative.TWO_SIDED)

    assert res.method == Method.TWO_PROPORTION_Z
    assert res.metric_type == MetricType.BINARY
    assert res.decision == Decision.REJECT_NULL
    assert res.is_significant

    assert res.statistic.name == "z"
    assert pytest.approx(res.statistic.value, abs=0.01) == 6.383
    assert pytest.approx(res.p_value, rel=1e-1) == 1.7e-10
    assert res.p_value_source == PValueSource.ANALYTIC

    assert res.estimate.name == EstimateName.DIFFERENCE_OF_PROPORTIONS
    assert pytest.approx(res.estimate.value, abs=1e-4) == 0.013

    assert res.confidence_interval.method == CIMethod.NORMAL_APPROX_UNPOOLED
    assert pytest.approx(res.confidence_interval.lower, abs=0.001) == 0.0090
    assert pytest.approx(res.confidence_interval.upper, abs=0.001) == 0.0170

    assert res.effect_size.name == EffectSizeName.COHENS_H
    assert pytest.approx(res.effect_size.value, abs=0.001) == 0.0403


def test_two_proportion_z_warning_on_low_counts() -> None:
    # Événements rares
    a = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    b = [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    res = two_proportion_z(a, b)
    assert any(w.code == "LOW_EVENT_COUNT" for w in res.warnings)


def test_two_proportion_z_alternatives() -> None:
    a = [0] * 50 + [1] * 10
    b = [0] * 40 + [1] * 20
    res_greater = two_proportion_z(a, b, alternative=Alternative.GREATER)
    res_less = two_proportion_z(a, b, alternative=Alternative.LESS)

    assert res_greater.p_value < 0.05
    assert res_less.p_value > 0.5


def test_fisher_exact_scenario() -> None:
    a = [1] * 2 + [0] * 18
    b = [1] * 12 + [0] * 8
    res = fisher_exact(a, b, alpha=0.05)

    assert res.method == Method.FISHER_EXACT
    assert res.metric_type == MetricType.BINARY
    assert res.confidence_interval.method == CIMethod.NEWCOMBE
    assert res.p_value_source == PValueSource.EXACT
    assert res.decision == Decision.REJECT_NULL
