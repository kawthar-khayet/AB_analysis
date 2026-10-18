"""Tests du contrat ``StatisticalResult`` (étape 1).

Ce fichier ne teste aucune valeur statistique : il vérifie que le contrat
**refuse les objets incohérents**. Les valeurs seront testées avec les méthodes.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from ab_stats.results import (
    EFFECT_DIRECTION,
    Alternative,
    AnalysisWarning,
    Assumption,
    AssumptionStatus,
    CIMethod,
    ConfidenceInterval,
    Decision,
    EffectSize,
    EffectSizeLabel,
    EffectSizeName,
    Estimate,
    EstimateName,
    GroupSummary,
    Groups,
    Hypotheses,
    Interpretation,
    InterpretationCase,
    Method,
    MetricType,
    PValueSource,
    Reproducibility,
    Severity,
    Statistic,
    StatisticalResult,
)

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def reproducibility(**overrides) -> Reproducibility:
    fields = {"computed_at": NOW, "input_hash": "sha256:abc"}
    fields.update(overrides)
    return Reproducibility(**fields)


def result(**overrides) -> StatisticalResult:
    """Résultat valide inspiré du scénario de référence du rapport."""
    fields = dict(
        method=Method.TWO_PROPORTION_Z,
        metric_type=MetricType.BINARY,
        hypotheses=Hypotheses(
            alternative=Alternative.TWO_SIDED,
            null_text="Les taux de conversion de A et B sont égaux.",
            alternative_text="Les taux de conversion de A et B diffèrent.",
        ),
        groups=Groups(
            a=GroupSummary(n=50_000, successes=5_550, rate=0.111),
            b=GroupSummary(n=50_000, successes=6_200, rate=0.124),
        ),
        statistic=Statistic(name="z", value=6.383),
        alpha=0.05,
        decision=Decision.REJECT_NULL,
        estimate=Estimate(
            name=EstimateName.DIFFERENCE_OF_PROPORTIONS, value=0.013, unit="proportion"
        ),
        confidence_interval=ConfidenceInterval(
            level=0.95, lower=0.009, upper=0.017, method=CIMethod.NORMAL_APPROX_UNPOOLED
        ),
        effect_size=EffectSize(name=EffectSizeName.COHENS_H, value=0.0403),
        reproducibility=reproducibility(),
        p_value=1.7e-10,
        p_value_source=PValueSource.ANALYTIC,
    )
    fields.update(overrides)
    return StatisticalResult(**fields)


# ---------------------------------------------------------------------------
# Immuabilité
# ---------------------------------------------------------------------------


def test_a_valid_result_can_be_built_by_hand() -> None:
    built = result()

    assert built.is_significant
    assert not built.has_critical_warning
    assert built.estimate.direction == EFFECT_DIRECTION


def test_result_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        result().p_value = 0.5  # type: ignore[misc]


def test_nested_objects_are_immutable() -> None:
    built = result()

    with pytest.raises(dataclasses.FrozenInstanceError):
        built.confidence_interval.lower = -1.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        built.groups.a.n = 1  # type: ignore[misc]


def test_collections_must_be_tuples() -> None:
    warning = AnalysisWarning(code="SMALL_SAMPLE", severity=Severity.INFO, message="n < 30")

    with pytest.raises(TypeError):
        result(warnings=[warning])
    with pytest.raises(TypeError):
        result(assumptions=[])


# ---------------------------------------------------------------------------
# p-value et verdict
# ---------------------------------------------------------------------------


def test_p_value_requires_its_source() -> None:
    with pytest.raises(ValueError, match="provenance"):
        result(p_value_source=None)


def test_source_without_p_value_is_refused() -> None:
    with pytest.raises(ValueError):
        result(p_value=None, decision=Decision.NOT_APPLICABLE)


def test_p_value_outside_unit_interval_is_refused() -> None:
    with pytest.raises(ValueError):
        result(p_value=1.5)


@pytest.mark.parametrize(
    ("p_value", "decision"),
    [(0.01, Decision.FAIL_TO_REJECT_NULL), (0.20, Decision.REJECT_NULL)],
)
def test_decision_must_match_p_value(p_value: float, decision: Decision) -> None:
    with pytest.raises(ValueError, match="incohérent"):
        result(p_value=p_value, decision=decision)


def test_p_value_equal_to_alpha_rejects() -> None:
    assert result(p_value=0.05, decision=Decision.REJECT_NULL).is_significant


def test_result_without_p_value_is_allowed() -> None:
    built = result(p_value=None, p_value_source=None, decision=Decision.NOT_APPLICABLE)

    assert not built.is_significant


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1])
def test_alpha_must_be_in_open_unit_interval(alpha: float) -> None:
    with pytest.raises(ValueError):
        result(alpha=alpha)


# ---------------------------------------------------------------------------
# Intervalle de confiance
# ---------------------------------------------------------------------------


def test_interval_with_one_bound_is_refused() -> None:
    with pytest.raises(ValueError, match="deux bornes"):
        ConfidenceInterval(level=0.95, lower=0.1, method=CIMethod.WALD)


def test_interval_bounds_require_a_construction_method() -> None:
    with pytest.raises(ValueError, match="construction"):
        ConfidenceInterval(level=0.95, lower=0.1, upper=0.2)


def test_method_without_bounds_is_refused() -> None:
    with pytest.raises(ValueError):
        ConfidenceInterval(level=0.95, method=CIMethod.WALD)


def test_inverted_bounds_are_refused() -> None:
    with pytest.raises(ValueError, match="inversées"):
        ConfidenceInterval(level=0.95, lower=0.2, upper=0.1, method=CIMethod.WALD)


def test_unavailable_interval_cannot_say_if_it_excludes_zero() -> None:
    interval = ConfidenceInterval(level=0.95)

    assert not interval.is_available
    with pytest.raises(ValueError):
        interval.excludes_zero


@pytest.mark.parametrize(
    ("lower", "upper", "excludes"),
    [(0.1, 0.2, True), (-0.2, -0.1, True), (-0.1, 0.2, False), (0.0, 0.2, False)],
)
def test_excludes_zero(lower: float, upper: float, excludes: bool) -> None:
    interval = ConfidenceInterval(level=0.95, lower=lower, upper=upper, method=CIMethod.WALD)

    assert interval.excludes_zero is excludes


# ---------------------------------------------------------------------------
# Estimé, taille d'effet, sous-objets
# ---------------------------------------------------------------------------


def test_estimate_direction_is_fixed() -> None:
    with pytest.raises(ValueError, match="sens"):
        Estimate(
            name=EstimateName.DIFFERENCE_OF_MEANS, value=1.0, unit="euros", direction="A_minus_B"
        )


def test_estimate_requires_a_unit() -> None:
    with pytest.raises(ValueError, match="unité"):
        Estimate(name=EstimateName.DIFFERENCE_OF_MEANS, value=1.0, unit=" ")


def test_effect_size_label_requires_its_convention() -> None:
    with pytest.raises(ValueError, match="convention"):
        EffectSize(name=EffectSizeName.COHENS_H, value=0.04, label=EffectSizeLabel.NEGLIGIBLE)


def test_effect_size_label_with_convention_is_allowed() -> None:
    effect = EffectSize(
        name=EffectSizeName.COHENS_H,
        value=0.04,
        convention="cohen_1988",
        label=EffectSizeLabel.NEGLIGIBLE,
    )

    assert effect.label is EffectSizeLabel.NEGLIGIBLE


def test_successes_cannot_exceed_n() -> None:
    with pytest.raises(ValueError):
        GroupSummary(n=10, successes=11)


def test_named_statistic_is_required_when_valued() -> None:
    with pytest.raises(ValueError, match="nom"):
        Statistic(value=2.0)


def test_violated_assumptions_are_listed() -> None:
    violated = Assumption(
        code="EQUAL_VARIANCES", description="Variances égales", status=AssumptionStatus.VIOLATED
    )
    unverifiable = Assumption(
        code="INDEPENDENCE", description="Indépendance", status=AssumptionStatus.UNVERIFIABLE
    )

    built = result(assumptions=(violated, unverifiable))

    assert built.violated_assumptions == (violated,)


def test_critical_warning_is_detected() -> None:
    critical = AnalysisWarning(code="ZERO_VARIANCE", severity=Severity.CRITICAL, message="…")

    assert result(warnings=(critical,)).has_critical_warning


# ---------------------------------------------------------------------------
# Reproductibilité
# ---------------------------------------------------------------------------


def test_reproducibility_requires_a_timezone() -> None:
    with pytest.raises(ValueError, match="fuseau"):
        reproducibility(computed_at=datetime(2026, 10, 6, 12, 0))


def test_reproducibility_sorts_library_versions() -> None:
    built = reproducibility(library_versions={"scipy": "1.15", "numpy": "2.4"})

    assert built.library_versions == (("numpy", "2.4"), ("scipy", "1.15"))
    assert built.versions == {"numpy": "2.4", "scipy": "1.15"}


# ---------------------------------------------------------------------------
# Interprétation
# ---------------------------------------------------------------------------


def interpretation(case: InterpretationCase, delta: float | None) -> Interpretation:
    return Interpretation(
        case=case,
        significance_statement="…",
        practical_statement="…",
        recommendation="…",
        delta=delta,
    )


@pytest.mark.parametrize(
    "case",
    [InterpretationCase.A, InterpretationCase.B, InterpretationCase.C, InterpretationCase.D],
)
def test_cases_a_to_d_require_delta(case: InterpretationCase) -> None:
    with pytest.raises(ValueError, match="delta"):
        interpretation(case, delta=None)


def test_case_e_does_not_require_delta() -> None:
    assert interpretation(InterpretationCase.E, delta=None).delta is None


def test_negative_delta_is_refused() -> None:
    with pytest.raises(ValueError):
        interpretation(InterpretationCase.A, delta=-0.01)
