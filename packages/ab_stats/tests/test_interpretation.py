"""Tests de l'arbre d'interprétation déterministe (étape 9)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from ab_stats.interpretation import interpret
from ab_stats.results import (
    Alternative,
    CIMethod,
    ConfidenceInterval,
    Decision,
    EffectSize,
    EffectSizeName,
    Estimate,
    EstimateName,
    GroupSummary,
    Groups,
    Hypotheses,
    InterpretationCase,
    Method,
    MetricType,
    PValueSource,
    Reproducibility,
    Statistic,
    StatisticalResult,
)


def _make_result(lower: float, upper: float, estimate: float, p_val: float) -> StatisticalResult:
    decision = Decision.REJECT_NULL if p_val <= 0.05 else Decision.FAIL_TO_REJECT_NULL
    return StatisticalResult(
        method=Method.WELCH_T,
        metric_type=MetricType.CONTINUOUS,
        hypotheses=Hypotheses(
            alternative=Alternative.TWO_SIDED,
            null_text="H0",
            alternative_text="H1",
        ),
        groups=Groups(
            a=GroupSummary(n=50, mean=10.0, sd=2.0),
            b=GroupSummary(n=50, mean=10.0 + estimate, sd=2.0),
        ),
        statistic=Statistic(name="t", value=2.0, df=98.0),
        alpha=0.05,
        decision=decision,
        estimate=Estimate(
            name=EstimateName.DIFFERENCE_OF_MEANS,
            value=estimate,
            unit="sec",
        ),
        confidence_interval=ConfidenceInterval(
            level=0.95,
            lower=lower,
            upper=upper,
            method=CIMethod.WELCH_T_DIST,
        ),
        effect_size=EffectSize(name=EffectSizeName.COHENS_D, value=estimate / 2.0),
        reproducibility=Reproducibility(
            computed_at=datetime.now(timezone.utc),
            input_hash="sha256:test",
        ),
        p_value=p_val,
        p_value_source=PValueSource.ANALYTIC,
    )


def test_mandatory_cases_from_plan() -> None:
    # Cas obligatoires :
    # IC [−0,3 ; +0,5] avec δ = 1,0 → case = "c"
    res_c = _make_result(lower=-0.3, upper=0.5, estimate=0.1, p_val=0.40)
    interp_c = interpret(res_c, delta=1.0)
    assert interp_c is not None
    assert interp_c.case == InterpretationCase.C

    # IC [−1,5 ; +4,1] avec δ = 1,0 → case = "d"
    res_d = _make_result(lower=-1.5, upper=4.1, estimate=1.3, p_val=0.15)
    interp_d = interpret(res_d, delta=1.0)
    assert interp_d is not None
    assert interp_d.case == InterpretationCase.D


def test_case_a_and_b() -> None:
    # Cas (a) : Tout l'IC est au-dessus de delta
    res_a = _make_result(lower=1.2, upper=2.5, estimate=1.8, p_val=0.001)
    interp_a = interpret(res_a, delta=1.0)
    assert interp_a is not None
    assert interp_a.case == InterpretationCase.A

    # Cas (b) : Exclut 0, mais sous delta
    res_b = _make_result(lower=0.1, upper=0.8, estimate=0.4, p_val=0.02)
    interp_b = interpret(res_b, delta=1.0)
    assert interp_b is not None
    assert interp_b.case == InterpretationCase.B


def test_case_e_negative_effect() -> None:
    # Cas (e) : Tout l'IC est en dessous de 0
    res_e = _make_result(lower=-2.5, upper=-0.5, estimate=-1.5, p_val=0.005)
    interp_e = interpret(res_e, delta=1.0)
    assert interp_e is not None
    assert interp_e.case == InterpretationCase.E

    # Même sans delta, le cas E fonctionne
    interp_e_no_delta = interpret(res_e, delta=None)
    assert interp_e_no_delta is not None
    assert interp_e_no_delta.case == InterpretationCase.E


def test_no_equality_statement_in_wording() -> None:
    # Règle absolue : aucune phrase ne doit contenir "égaux" ou équivalent
    forbidden_words = ["égaux", "egaux", "égales", "egales", "identiques", "pas de différence"]
    for lower, upper, est, p in [
        (-0.3, 0.5, 0.1, 0.4),
        (-1.5, 4.1, 1.3, 0.2),
        (1.2, 2.5, 1.8, 0.001),
        (0.1, 0.8, 0.4, 0.02),
        (-2.5, -0.5, -1.5, 0.01),
    ]:
        res = _make_result(lower, upper, est, p)
        interp = interpret(res, delta=1.0)
        assert interp is not None
        all_text = (
            f"{interp.significance_statement} {interp.practical_statement} {interp.recommendation}"
        ).lower()
        for word in forbidden_words:
            assert word not in all_text, f"Le mot interdit '{word}' a été trouvé dans: {all_text}"
