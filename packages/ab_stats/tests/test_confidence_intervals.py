"""Tests des constructions d'intervalles de confiance (étape 5)."""

from __future__ import annotations

import math
import numpy as np
import pytest

from ab_stats.confidence_intervals import (
    hodges_lehmann_ci,
    newcombe_proportion_ci,
    percentile_bootstrap_ci,
    student_mean_ci,
    unpooled_proportion_ci,
    welch_mean_ci,
)
from ab_stats.results import CIMethod


def test_unpooled_proportion_ci() -> None:
    # 5 550 / 50 000 (0.111) vs 6 200 / 50 000 (0.124)
    # Rapport §13 : diff = 0.013, IC 95% ≈ [+0.0090, +0.0170]
    ci = unpooled_proportion_ci(rate_a=0.111, n_a=50_000, rate_b=0.124, n_b=50_000, confidence_level=0.95)
    assert ci.method == CIMethod.NORMAL_APPROX_UNPOOLED
    assert ci.level == 0.95
    assert pytest.approx(ci.lower, abs=0.001) == 0.009
    assert pytest.approx(ci.upper, abs=0.001) == 0.017
    assert ci.excludes_zero


def test_newcombe_proportion_ci() -> None:
    ci = newcombe_proportion_ci(rate_a=0.10, n_a=100, rate_b=0.20, n_b=100, confidence_level=0.95)
    assert ci.method == CIMethod.NEWCOMBE
    assert ci.lower < 0.10 < ci.upper
    assert ci.lower > 0.0  # exclut 0


def test_welch_and_student_mean_ci() -> None:
    # Cas symétrique
    ci_welch = welch_mean_ci(mean_a=10.0, sd_a=2.0, n_a=50, mean_b=12.0, sd_b=2.0, n_b=50, confidence_level=0.95)
    ci_student = student_mean_ci(mean_a=10.0, sd_a=2.0, n_a=50, mean_b=12.0, sd_b=2.0, n_b=50, confidence_level=0.95)

    assert ci_welch.method == CIMethod.WELCH_T_DIST
    assert ci_student.method == CIMethod.STUDENT_T_DIST
    # Avec variances et n égaux, Welch et Student sont quasi identiques
    assert pytest.approx(ci_welch.lower, rel=1e-2) == ci_student.lower
    assert pytest.approx(ci_welch.upper, rel=1e-2) == ci_student.upper
    assert ci_welch.lower < 2.0 < ci_welch.upper


def test_hodges_lehmann_ci() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    b = np.array([3.0, 4.0, 5.0, 6.0, 7.0])
    ci = hodges_lehmann_ci(a, b, confidence_level=0.95)
    assert ci.method == CIMethod.HODGES_LEHMANN
    assert ci.lower <= 2.0 <= ci.upper


def test_percentile_bootstrap_ci() -> None:
    rng = np.random.default_rng(42)
    diffs = rng.normal(loc=1.5, scale=0.5, size=2000)
    ci = percentile_bootstrap_ci(diffs, confidence_level=0.95)
    assert ci.method == CIMethod.PERCENTILE_BOOTSTRAP
    assert ci.lower < 1.5 < ci.upper
    assert pytest.approx(ci.lower, abs=0.1) == 1.5 - 1.96 * 0.5
