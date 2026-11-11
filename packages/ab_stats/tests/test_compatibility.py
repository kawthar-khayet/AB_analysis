"""Tests du moteur de compatibilité (étape 8)."""

from __future__ import annotations

import numpy as np

from ab_stats.compatibility import evaluate_compatibility, get_compatible_methods
from ab_stats.data import (
    BinaryEncoding,
    GroupMapping,
    MetricDeclaration,
    normalize,
)
from ab_stats.diagnostics import diagnose
from ab_stats.results import Method, MetricType


def test_binary_compatibility() -> None:
    # Métrique binaire normale
    groups = ["control"] * 50 + ["treatment"] * 50
    metrics = ["0"] * 40 + ["1"] * 10 + ["0"] * 35 + ["1"] * 15

    dataset = normalize(
        groups,
        metrics,
        mapping=GroupMapping("control", "treatment"),
        declaration=MetricDeclaration(metric_type=MetricType.BINARY, binary_encoding=BinaryEncoding("0", "1")),
    )
    diagnostics = diagnose(dataset)
    comp = evaluate_compatibility(diagnostics)

    # z-test et fisher sont compatibles
    assert comp[Method.TWO_PROPORTION_Z].compatible
    assert comp[Method.FISHER_EXACT].compatible

    # Les méthodes continues sont déclarées incompatibles
    assert not comp[Method.WELCH_T].compatible
    assert not comp[Method.BOOTSTRAP].compatible
    assert set(comp) == set(Method)

    # Méthodes compatibles : uniquement z et fisher
    compatible = get_compatible_methods(diagnostics)
    assert set(compatible) == {Method.TWO_PROPORTION_Z, Method.FISHER_EXACT}


def test_binary_low_counts_warning_and_recommendation() -> None:
    # Très peu d'événements
    groups = ["control"] * 20 + ["treatment"] * 20
    metrics = ["0"] * 18 + ["1"] * 2 + ["0"] * 19 + ["1"] * 1

    dataset = normalize(
        groups,
        metrics,
        mapping=GroupMapping("control", "treatment"),
        declaration=MetricDeclaration(metric_type=MetricType.BINARY, binary_encoding=BinaryEncoding("0", "1")),
    )
    diagnostics = diagnose(dataset)
    comp = evaluate_compatibility(diagnostics)

    assert comp[Method.TWO_PROPORTION_Z].compatible
    assert any(w.code == "LOW_EVENT_COUNT" for w in comp[Method.TWO_PROPORTION_Z].warnings)
    # Fisher exact est recommandé dans ce cas
    assert comp[Method.FISHER_EXACT].is_recommended
    assert not comp[Method.TWO_PROPORTION_Z].is_recommended


def test_continuous_skewed_recommends_bootstrap() -> None:
    rng = np.random.default_rng(42)
    # Données asymétriques
    a = list(rng.exponential(scale=1.0, size=100))
    b = list(rng.exponential(scale=3.0, size=100))
    groups = ["control"] * 100 + ["treatment"] * 100
    metrics = [str(x) for x in a + b]

    dataset = normalize(
        groups,
        metrics,
        mapping=GroupMapping("control", "treatment"),
        declaration=MetricDeclaration(metric_type=MetricType.CONTINUOUS, unit="sec"),
    )
    diagnostics = diagnose(dataset)
    comp = evaluate_compatibility(diagnostics)

    assert comp[Method.WELCH_T].compatible
    assert comp[Method.BOOTSTRAP].compatible
    # Incompatible avec les méthodes binaires
    assert not comp[Method.TWO_PROPORTION_Z].compatible
    assert not comp[Method.FISHER_EXACT].compatible

    # Le bootstrap (sans hypothèse de normalité) est recommandé en présence de forte asymétrie
    assert comp[Method.BOOTSTRAP].is_recommended
    assert not comp[Method.WELCH_T].is_recommended
