"""Tests du test de permutation (étape 18)."""

from __future__ import annotations

import numpy as np
import pytest

from ab_stats.analyses.resampling import permutation_test
from ab_stats.results import CIMethod, Decision, Method, PValueSource


def test_permutation_test_deterministic_reproducibility() -> None:
    a = [10.0, 11.0, 12.0, 13.0, 14.0]
    b = [15.0, 16.0, 17.0, 18.0, 19.0]

    res1 = permutation_test(a, b, n_resamples=500, seed=123)
    res2 = permutation_test(a, b, n_resamples=500, seed=123)

    assert res1.method == Method.PERMUTATION
    assert res1.p_value == res2.p_value
    assert res1.statistic.value == res2.statistic.value
    assert res1.p_value_source == PValueSource.PERMUTATION
    assert res1.confidence_interval.method == CIMethod.PERCENTILE_BOOTSTRAP
    assert res1.decision == Decision.REJECT_NULL


def test_permutation_test_null_case() -> None:
    rng = np.random.default_rng(999)
    a = rng.normal(10, 2, 40)
    b = rng.normal(10, 2, 40)

    res = permutation_test(a, b, n_resamples=1000, seed=42)
    assert res.p_value > 0.05
    assert res.decision == Decision.FAIL_TO_REJECT_NULL
