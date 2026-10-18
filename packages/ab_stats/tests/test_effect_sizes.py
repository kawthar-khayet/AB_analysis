"""Tests des tailles d'effet (étape 5)."""

from __future__ import annotations

import math
import numpy as np
import pytest

from ab_stats.effect_sizes import (
    build_cliffs_delta,
    build_cohens_d,
    build_cohens_h,
    build_hedges_g,
    cliffs_delta,
    cohens_d,
    cohens_h,
    hedges_g,
    label_cliffs_delta,
    label_cohens_d,
    label_cohens_h,
)
from ab_stats.results import EffectSizeLabel, EffectSizeName


def test_cohens_h_report_examples() -> None:
    # Rapport §13 : cohens_h(0.01, 0.02) ≈ 0.084 et cohens_h(0.50, 0.51) ≈ 0.020
    h1 = cohens_h(0.01, 0.02)
    assert pytest.approx(h1, abs=0.001) == 0.0835
    assert label_cohens_h(h1) == EffectSizeLabel.NEGLIGIBLE

    h2 = cohens_h(0.50, 0.51)
    assert pytest.approx(h2, abs=0.001) == 0.0200
    assert label_cohens_h(h2) == EffectSizeLabel.NEGLIGIBLE


def test_cohens_h_labels() -> None:
    assert label_cohens_h(0.1) == EffectSizeLabel.NEGLIGIBLE
    assert label_cohens_h(0.3) == EffectSizeLabel.SMALL
    assert label_cohens_h(0.6) == EffectSizeLabel.MEDIUM
    assert label_cohens_h(0.9) == EffectSizeLabel.LARGE


def test_cohens_d_and_hedges_g() -> None:
    # Cas connu : A = N(0, 1), B = N(1, 1), sd = 1 -> d = 1.0
    d = cohens_d(mean_a=10.0, mean_b=12.0, sd_a=2.0, sd_b=2.0, n_a=50, n_b=50)
    assert pytest.approx(d) == 1.0
    assert label_cohens_d(d) == EffectSizeLabel.LARGE

    g = hedges_g(d, n_a=50, n_b=50)
    # df = 98 -> facteur correction < 1
    assert 0.99 < g < 1.0


def test_cliffs_delta() -> None:
    # Groupe B strictement supérieur à A
    a = [1, 2, 3]
    b = [4, 5, 6]
    delta = cliffs_delta(a, b)
    assert delta == 1.0
    assert label_cliffs_delta(delta) == EffectSizeLabel.LARGE

    # Groupes identiques
    delta_zero = cliffs_delta([1, 2, 3], [1, 2, 3])
    assert delta_zero == 0.0
    assert label_cliffs_delta(delta_zero) == EffectSizeLabel.NEGLIGIBLE


def test_build_effect_sizes() -> None:
    res_h = build_cohens_h(0.10, 0.15)
    assert res_h.name == EffectSizeName.COHENS_H
    assert res_h.convention == "cohen_1988"
    assert res_h.label is not None

    res_d = build_cohens_d(10.0, 11.0, 1.0, 1.0, 30, 30)
    assert res_d.name == EffectSizeName.COHENS_D
    assert res_d.convention == "cohen_1988"

    res_delta = build_cliffs_delta([1, 2, 3], [2, 3, 4])
    assert res_delta.name == EffectSizeName.CLIFFS_DELTA
    assert res_delta.convention == "romano_2006"
