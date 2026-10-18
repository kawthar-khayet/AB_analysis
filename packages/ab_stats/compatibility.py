"""Moteur de compatibilité des méthodes statistiques.

Ce module examine la nature de la métrique et les diagnostics pour évaluer,
pour chacune des 7 méthodes du catalogue :
1. Sa compatibilité (booléen + motif en cas d'incompatibilité).
2. Les hypothèses de validité requises.
3. Les avertissements pertinents (avertissements machine-readable).
4. La recommandation par défaut.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ab_stats.diagnostics import Diagnostics
from ab_stats.results import (
    AnalysisWarning,
    Assumption,
    AssumptionStatus,
    Method,
    MetricType,
    Severity,
)

__all__ = [
    "MethodCompatibility",
    "evaluate_compatibility",
    "get_compatible_methods",
]


@dataclass(frozen=True, slots=True)
class MethodCompatibility:
    """Diagnostic d'adéquation d'une méthode pour un jeu de données."""

    method: Method
    compatible: bool
    reason: str | None = None
    assumptions: tuple[Assumption, ...] = ()
    warnings: tuple[AnalysisWarning, ...] = ()
    is_recommended: bool = False


def evaluate_compatibility(diagnostics: Diagnostics) -> dict[Method, MethodCompatibility]:
    """Évalue l'adéquation des 7 méthodes à partir du diagnostic du jeu de données."""
    metric_type = diagnostics.metric_type
    results: dict[Method, MethodCompatibility] = {}

    # Extraction des constats diagnostiques
    diag_warning_codes = {w.code: w for w in diagnostics.warnings}

    has_low_events = "LOW_EVENT_COUNT" in diag_warning_codes or "ZERO_EVENTS" in diag_warning_codes
    has_small_sample = "SMALL_SAMPLE" in diag_warning_codes
    has_skewness = "HIGH_SKEWNESS" in diag_warning_codes
    has_outliers = "OUTLIERS_DETECTED" in diag_warning_codes
    has_unequal_vars = "UNEQUAL_VARIANCES" in diag_warning_codes
    has_zero_var = "ZERO_VARIANCE" in diag_warning_codes
    has_unbalanced = "UNBALANCED_GROUPS" in diag_warning_codes

    # 1. Méthodes binaires
    if metric_type is MetricType.BINARY:
        # TWO_PROPORTION_Z
        z_warnings: list[AnalysisWarning] = []
        z_status = AssumptionStatus.SATISFIED
        if has_low_events:
            z_status = AssumptionStatus.VIOLATED
            z_warnings.append(
                AnalysisWarning(
                    code="LOW_EVENT_COUNT",
                    severity=Severity.WARNING,
                    message="Effectif d'événements faible (< 10). L'approximation normale est dégradée.",
                    suggested_alternative=Method.FISHER_EXACT,
                )
            )
        if has_unbalanced:
            z_warnings.append(diag_warning_codes["UNBALANCED_GROUPS"])

        results[Method.TWO_PROPORTION_Z] = MethodCompatibility(
            method=Method.TWO_PROPORTION_Z,
            compatible=True,
            assumptions=(
                Assumption(code="INDEPENDENCE", description="Observations indépendantes.", status=AssumptionStatus.UNVERIFIABLE),
                Assumption(code="BINARY", description="Métrique strictement binaire.", status=AssumptionStatus.SATISFIED),
                Assumption(code="NORMAL_APPROX", description="Au moins 10 événements par groupe.", status=z_status),
            ),
            warnings=tuple(z_warnings),
            is_recommended=not has_low_events,
        )

        # FISHER_EXACT
        results[Method.FISHER_EXACT] = MethodCompatibility(
            method=Method.FISHER_EXACT,
            compatible=True,
            assumptions=(
                Assumption(code="INDEPENDENCE", description="Observations indépendantes.", status=AssumptionStatus.UNVERIFIABLE),
                Assumption(code="BINARY", description="Métrique strictement binaire.", status=AssumptionStatus.SATISFIED),
                Assumption(code="EXACT_CONDITIONAL", description="Test conditionnel exact sur table 2x2.", status=AssumptionStatus.SATISFIED),
            ),
            warnings=(),
            is_recommended=has_low_events,
        )

        # Méthodes continues incompatibles
        for m in (Method.WELCH_T, Method.STUDENT_T, Method.MANN_WHITNEY_U, Method.PERMUTATION, Method.BOOTSTRAP):
            results[m] = MethodCompatibility(
                method=m,
                compatible=False,
                reason="Cette méthode s'applique aux métriques continues, pas aux métriques binaires.",
            )

    # 2. Méthodes continues
    else:
        # Méthodes binaires incompatibles
        results[Method.TWO_PROPORTION_Z] = MethodCompatibility(
            method=Method.TWO_PROPORTION_Z,
            compatible=False,
            reason="Le test de proportions s'applique uniquement aux métriques binaires.",
        )
        results[Method.FISHER_EXACT] = MethodCompatibility(
            method=Method.FISHER_EXACT,
            compatible=False,
            reason="Le test exact de Fisher s'applique uniquement aux métriques binaires.",
        )

        # Warnings partagés pour tests t
        continuous_common_warnings: list[AnalysisWarning] = []
        if has_small_sample:
            continuous_common_warnings.append(diag_warning_codes["SMALL_SAMPLE"])
        if has_skewness:
            continuous_common_warnings.append(diag_warning_codes["HIGH_SKEWNESS"])
        if has_outliers:
            continuous_common_warnings.append(diag_warning_codes["OUTLIERS_DETECTED"])
        if has_unbalanced:
            continuous_common_warnings.append(diag_warning_codes["UNBALANCED_GROUPS"])

        # WELCH_T (recommandé par défaut)
        results[Method.WELCH_T] = MethodCompatibility(
            method=Method.WELCH_T,
            compatible=not has_zero_var,
            reason="Variance nulle dans les données." if has_zero_var else None,
            assumptions=(
                Assumption(code="INDEPENDENCE", description="Observations indépendantes.", status=AssumptionStatus.UNVERIFIABLE),
                Assumption(code="NORMALITY_OF_MEANS", description="Normalité approximative des moyennes (TCL).", status=AssumptionStatus.SATISFIED if not has_small_sample else AssumptionStatus.UNVERIFIABLE),
            ),
            warnings=tuple(continuous_common_warnings),
            is_recommended=(not has_skewness and not has_outliers and not has_zero_var),
        )

        # STUDENT_T (déconseillé si variances inégales)
        student_warnings = list(continuous_common_warnings)
        student_homo_status = AssumptionStatus.SATISFIED
        if has_unequal_vars:
            student_homo_status = AssumptionStatus.VIOLATED
            student_warnings.append(
                AnalysisWarning(
                    code="UNEQUAL_VARIANCES",
                    severity=Severity.WARNING,
                    message="Variances hétérogènes entre groupes. Préférez le test de Welch.",
                    suggested_alternative=Method.WELCH_T,
                )
            )

        results[Method.STUDENT_T] = MethodCompatibility(
            method=Method.STUDENT_T,
            compatible=not has_zero_var,
            reason="Variance nulle dans les données." if has_zero_var else None,
            assumptions=(
                Assumption(code="INDEPENDENCE", description="Observations indépendantes.", status=AssumptionStatus.UNVERIFIABLE),
                Assumption(code="NORMALITY", description="Normalité de la distribution.", status=AssumptionStatus.SATISFIED if not has_skewness else AssumptionStatus.VIOLATED),
                Assumption(code="HOMOSCEDASTICITY", description="Égalité des variances.", status=student_homo_status),
            ),
            warnings=tuple(student_warnings),
            is_recommended=False,  # Welch est toujours le défaut
        )

        # MANN_WHITNEY_U (recommandé si skewness ou outliers)
        results[Method.MANN_WHITNEY_U] = MethodCompatibility(
            method=Method.MANN_WHITNEY_U,
            compatible=True,
            assumptions=(
                Assumption(code="INDEPENDENCE", description="Observations indépendantes.", status=AssumptionStatus.UNVERIFIABLE),
                Assumption(code="ORDINAL_SCALE", description="Métrique au moins ordinale.", status=AssumptionStatus.SATISFIED),
            ),
            warnings=(),
            is_recommended=(has_skewness or has_outliers),
        )

        # PERMUTATION
        results[Method.PERMUTATION] = MethodCompatibility(
            method=Method.PERMUTATION,
            compatible=True,
            assumptions=(
                Assumption(code="EXCHANGEABILITY", description="Échangeabilité des observations sous H0.", status=AssumptionStatus.SATISFIED),
                Assumption(code="INDEPENDENCE", description="Observations indépendantes.", status=AssumptionStatus.UNVERIFIABLE),
            ),
            warnings=(),
            is_recommended=False,
        )

        # BOOTSTRAP
        boot_warnings = [diag_warning_codes["SMALL_SAMPLE"]] if has_small_sample else []
        results[Method.BOOTSTRAP] = MethodCompatibility(
            method=Method.BOOTSTRAP,
            compatible=True,
            assumptions=(
                Assumption(code="REPRESENTATIVENESS", description="Échantillon représentatif de la population.", status=AssumptionStatus.SATISFIED if not has_small_sample else AssumptionStatus.UNVERIFIABLE),
                Assumption(code="INDEPENDENCE", description="Observations indépendantes.", status=AssumptionStatus.UNVERIFIABLE),
            ),
            warnings=tuple(boot_warnings),
            is_recommended=False,
        )

    return results


def get_compatible_methods(diagnostics: Diagnostics) -> list[Method]:
    """Retourne la liste ordonnée des méthodes compatibles."""
    comp = evaluate_compatibility(diagnostics)
    return [m for m, c in comp.items() if c.compatible]
