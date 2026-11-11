"""Arbre de décision déterministe pour l'interprétation des résultats (étape 9).

Ce module applique les 5 cas (a -> e) du rapport §15 à la lumière du seuil
de pertinence pratique delta fixé par l'analyste :

* (a) IC entièrement au-delà de delta : significatif ET pertinent -> Déployer B.
* (b) IC exclut 0 mais reste sous delta : significatif, mais négligeable -> Ne pas déployer.
* (c) IC contient 0 et tient dans ±delta : non concluant, mais gros effet exclu -> Arrêter.
* (d) IC contient 0 et dépasse delta : non concluant, étude trop imprécise -> Relancer avec plus de données.
* (e) IC entièrement du côté défavorable : effet négatif significatif -> Ne pas déployer (B dégrade la métrique).

**Sens favorable.** L'arbre raisonne sur le *gain* apporté par B, pas sur le signe
brut de B − A. Pour une métrique où « plus haut = mieux » (taux de recouvrement,
conversion), le gain est B − A. Pour une métrique où « plus bas = mieux » (délai de
paiement, taux de défaut), le gain est A − B : l'IC est retourné avant d'appliquer
l'arbre. L'estimé et l'IC du résultat restent, eux, exprimés en B − A.

Règle absolue : aucune phrase ne doit affirmer que A et B sont égaux.
"""

from __future__ import annotations

import math

from ab_stats.exceptions import InvalidParameterError
from ab_stats.results import (
    FavorableDirection,
    Interpretation,
    InterpretationCase,
    StatisticalResult,
)

__all__ = [
    "interpret",
]

_LOWER_IS_BETTER_NOTE = (
    "Sens favorable déclaré : plus bas = mieux. Une différence B − A négative "
    "est donc lue comme une amélioration apportée par B."
)


def _normalize_direction(direction: FavorableDirection | str) -> FavorableDirection:
    try:
        return FavorableDirection(direction)
    except ValueError:
        raise InvalidParameterError(
            "INVALID_FAVORABLE_DIRECTION",
            "Le sens favorable doit valoir 'higher_is_better' ou 'lower_is_better'.",
            details={
                "favorable_direction": str(direction),
                "allowed": [d.value for d in FavorableDirection],
            },
        ) from None


def interpret(
    result: StatisticalResult,
    delta: float | None = None,
    favorable_direction: FavorableDirection | str = FavorableDirection.HIGHER_IS_BETTER,
) -> Interpretation | None:
    """Interprète un résultat statistique à la lumière d'un seuil delta et du sens favorable."""
    direction = _normalize_direction(favorable_direction)
    ci = result.confidence_interval
    if not ci.is_available or ci.lower is None or ci.upper is None:
        return None

    if delta is not None:
        if not math.isfinite(delta) or delta < 0:
            raise InvalidParameterError(
                "INVALID_DELTA",
                "Le seuil de pertinence pratique delta doit être un nombre fini positif ou nul.",
                details={"delta": delta},
            )

    # IC et estimé exprimés en « gain apporté par B » (positif = B meilleur).
    if direction is FavorableDirection.LOWER_IS_BETTER:
        lower, upper = -ci.upper, -ci.lower
        gain_estimate = -result.estimate.value
    else:
        lower, upper = ci.lower, ci.upper
        gain_estimate = result.estimate.value

    caveats = tuple(w.message for w in result.warnings)
    if direction is FavorableDirection.LOWER_IS_BETTER:
        caveats = (_LOWER_IS_BETTER_NOTE, *caveats)

    def build(case: InterpretationCase, significance: str, practical: str, recommendation: str) -> Interpretation:
        return Interpretation(
            case=case,
            delta=delta,
            significance_statement=significance,
            practical_statement=practical,
            recommendation=recommendation,
            caveats=caveats,
            favorable_direction=direction,
        )

    # Cas (e) : tout l'intervalle est du côté défavorable (B est pire qu'A de façon significative)
    if upper < 0.0:
        return build(
            InterpretationCase.E,
            "L'effet mesuré est statistiquement significatif en défaveur de la variante B.",
            "La variante B dégrade la métrique par rapport au contrôle A.",
            "Ne pas déployer la variante B.",
        )

    # Si delta est None, les cas A, B, C, D ne peuvent pas être déterminés
    if delta is None:
        return None

    # L'intervalle contient-il 0 ? (Non significatif)
    if lower <= 0.0 <= upper:
        # Cas (c) : contient 0, mais est entièrement compris dans [-delta, +delta]
        if lower >= -delta and upper <= delta:
            return build(
                InterpretationCase.C,
                "Les données ne fournissent pas de preuve statistique suffisante d'un effet.",
                (
                    f"L'intervalle de confiance est entièrement resserré dans ±{delta:.4g} : "
                    "un effet économiquement pertinent est exclu."
                ),
                "Arrêter l'expérimentation ; la variante B n'apporte pas de gain suffisant.",
            )
        # Cas (d) : contient 0, et dépasse le seuil delta
        return build(
            InterpretationCase.D,
            "Les données ne fournissent pas de preuve statistique suffisante d'un effet.",
            (
                f"L'intervalle de confiance dépasse le seuil de pertinence pratique ({delta:.4g}) : "
                "l'étude manque de précision pour trancher."
            ),
            "Poursuivre ou relancer l'expérience avec un effectif plus important.",
        )

    # Ici, lower > 0.0 : gain significatif en faveur de B
    # Cas (a) : entièrement au-delà de delta
    if lower >= delta:
        return build(
            InterpretationCase.A,
            "L'effet est statistiquement significatif.",
            (
                f"L'intervalle de confiance est entièrement au-delà du seuil de pertinence pratique ({delta:.4g}) : "
                "l'amélioration observée est substantielle."
            ),
            "Déployer la variante B.",
        )

    # Cas (b) : exclut 0, mais reste sous delta
    if upper <= delta:
        return build(
            InterpretationCase.B,
            "L'effet est statistiquement significatif.",
            f"Bien que statistiquement réel, le gain reste inférieur au seuil de pertinence pratique ({delta:.4g}).",
            "Ne pas déployer : le gain attendu ne justifie pas le coût de déploiement.",
        )

    # Chevauchement : lower < delta < upper (lower > 0).
    # L'estimé ponctuel départage : au-delà de delta -> (a) sous surveillance, sinon (b).
    if gain_estimate >= delta:
        return build(
            InterpretationCase.A,
            "L'effet est statistiquement significatif.",
            (
                f"L'effet estimé dépasse le seuil de pertinence pratique ({delta:.4g}), "
                "bien que la borne de l'IC la plus proche de 0 lui soit inférieure."
            ),
            "Déployer la variante B sous surveillance.",
        )

    return build(
        InterpretationCase.B,
        "L'effet est statistiquement significatif.",
        f"L'effet estimé reste inférieur au seuil de pertinence pratique ({delta:.4g}).",
        "Ne pas déployer : gain incertain sous le seuil économique.",
    )
