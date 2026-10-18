"""Arbre de décision déterministe pour l'interprétation des résultats (étape 9).

Ce module applique les 5 cas (a -> e) du rapport §15 à la lumière du seuil
de pertinence pratique delta fixé par l'analyste :

* (a) IC entièrement au-delà de delta : significatif ET pertinent -> Déployer B.
* (b) IC exclut 0 mais reste sous delta : significatif, mais négligeable -> Ne pas déployer.
* (c) IC contient 0 et tient dans ±delta : non concluant, mais gros effet exclu -> Arrêter.
* (d) IC contient 0 et dépasse delta : non concluant, étude trop imprécise -> Relancer avec plus de données.
* (e) IC entièrement sous 0 : effet négatif significatif -> Ne pas déployer (B dégrade la métrique).

Règle absolue : aucune phrase ne doit affirmer que A et B sont égaux.
"""

from __future__ import annotations

import math

from ab_stats.exceptions import InvalidParameterError
from ab_stats.results import (
    Interpretation,
    InterpretationCase,
    StatisticalResult,
)

__all__ = [
    "interpret",
]


def interpret(
    result: StatisticalResult,
    delta: float | None = None,
) -> Interpretation | None:
    """Interprète un résultat statistique à la lumière d'un seuil delta optionnel."""
    ci = result.confidence_interval
    if not ci.is_available or ci.lower is None or ci.upper is None:
        return None

    lower = ci.lower
    upper = ci.upper

    if delta is not None:
        if not math.isfinite(delta) or delta < 0:
            raise InvalidParameterError(
                "INVALID_DELTA",
                "Le seuil de pertinence pratique delta doit être un nombre fini positif ou nul.",
                details={"delta": delta},
            )

    # Cas (e) : Tout l'intervalle est négatif (B est pire qu'A de façon significative)
    if upper < 0.0:
        return Interpretation(
            case=InterpretationCase.E,
            delta=delta,
            significance_statement="L'effet mesuré est statistiquement significatif en défaveur de la variante B.",
            practical_statement="La variante B dégrade la métrique par rapport au contrôle A.",
            recommendation="Ne pas déployer la variante B.",
            caveats=tuple(w.message for w in result.warnings),
        )

    # Si delta est None, les cas A, B, C, D ne peuvent pas être déterminés
    if delta is None:
        return None

    # L'intervalle contient-il 0 ? (Non significatif)
    contains_zero = (lower <= 0.0 <= upper)

    if contains_zero:
        # Cas (c) : Contient 0, mais est entièrement compris dans [-delta, +delta]
        if lower >= -delta and upper <= delta:
            return Interpretation(
                case=InterpretationCase.C,
                delta=delta,
                significance_statement="Les données ne fournissent pas de preuve statistique suffisante d'un effet.",
                practical_statement=(
                    f"L'intervalle de confiance est entièrement resserré dans ±{delta:.4g} : "
                    "un effet économiquement pertinent est exclu."
                ),
                recommendation="Arrêter l'expérimentation ; la variante B n'apporte pas de gain suffisant.",
                caveats=tuple(w.message for w in result.warnings),
            )
        # Cas (d) : Contient 0, et dépasse le seuil delta
        return Interpretation(
            case=InterpretationCase.D,
            delta=delta,
            significance_statement="Les données ne fournissent pas de preuve statistique suffisante d'un effet.",
            practical_statement=(
                f"L'intervalle de confiance dépasse le seuil de pertinence pratique ({delta:.4g}) : "
                "l'étude manque de précision pour trancher."
            ),
            recommendation="Poursuivre ou relancer l'expérience avec un effectif plus important.",
            caveats=tuple(w.message for w in result.warnings),
        )

    # Ici, lower > 0.0 (Significatif positif)
    # Cas (a) : Entièrement au-delà de delta (ou estimation au-delà de delta si l'IC le traverse)
    if lower >= delta:
        return Interpretation(
            case=InterpretationCase.A,
            delta=delta,
            significance_statement="L'effet est statistiquement significatif.",
            practical_statement=(
                f"L'intervalle de confiance est entièrement supérieur au seuil de pertinence pratique ({delta:.4g}) : "
                "l'amélioration observée est substantielle."
            ),
            recommendation="Déployer la variante B.",
            caveats=tuple(w.message for w in result.warnings),
        )

    if upper <= delta:
        # Cas (b) : Exclut 0, mais reste sous delta
        return Interpretation(
            case=InterpretationCase.B,
            delta=delta,
            significance_statement="L'effet est statistiquement significatif.",
            practical_statement=(
                f"Bien que statistiquement réel, le gain reste inférieur au seuil de pertinence pratique ({delta:.4g})."
            ),
            recommendation="Ne pas déployer : le gain attendu ne justifie pas le coût de déploiement.",
            caveats=tuple(w.message for w in result.warnings),
        )

    # Chevauchement : lower < delta < upper (lower > 0)
    # Si la valeur ponctuelle dépasse delta, on conclut en faveur de A (pertinence probable), sinon B
    if result.estimate.value >= delta:
        return Interpretation(
            case=InterpretationCase.A,
            delta=delta,
            significance_statement="L'effet est statistiquement significatif.",
            practical_statement=(
                f"L'effet estimé dépasse le seuil de pertinence pratique ({delta:.4g}), "
                "bien que la borne basse de l'IC lui soit inférieure."
            ),
            recommendation="Déployer la variante B sous surveillance.",
            caveats=tuple(w.message for w in result.warnings),
        )

    return Interpretation(
        case=InterpretationCase.B,
        delta=delta,
        significance_statement="L'effet est statistiquement significatif.",
        practical_statement=(
            f"L'effet estimé reste inférieur au seuil de pertinence pratique ({delta:.4g})."
        ),
        recommendation="Ne pas déployer : gain incertain sous le seuil économique.",
        caveats=tuple(w.message for w in result.warnings),
    )
