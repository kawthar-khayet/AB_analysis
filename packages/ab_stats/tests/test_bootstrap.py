"""Tests du test bootstrap (étape 18)."""

from __future__ import annotations

import numpy as np
import pytest

from ab_stats.analyses.resampling import bootstrap_test
from ab_stats.results import CIMethod, Decision, Method, PValueSource


def test_bootstrap_test_significant_difference() -> None:
    rng = np.random.default_rng(2026)
    a = rng.normal(10, 1, 50)
    b = rng.normal(12, 1, 50)

    res = bootstrap_test(a, b, n_resamples=1000, seed=42)

    assert res.method == Method.BOOTSTRAP
    assert res.confidence_interval.method == CIMethod.PERCENTILE_BOOTSTRAP
    assert res.p_value_source == PValueSource.BOOTSTRAP_SHIFTED
    assert res.decision == Decision.REJECT_NULL
    assert res.confidence_interval.excludes_zero


def test_bootstrap_test_null_case() -> None:
    rng = np.random.default_rng(2027)
    a = rng.normal(10, 2, 50)
    b = rng.normal(10, 2, 50)

    res = bootstrap_test(a, b, n_resamples=1000, seed=42)
    assert res.decision == Decision.FAIL_TO_REJECT_NULL
    assert not res.confidence_interval.excludes_zero
