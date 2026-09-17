"""Erreurs structurées du paquet ``ab_stats``.

Toute erreur porte un ``code`` stable, un message lisible et des ``details``
exploitables par une machine. C'est ce qui permet au backend de renvoyer une
structure JSON au lieu d'une phrase figée, et au frontend de traduire, filtrer
ou afficher les valeurs en cause.

Deux niveaux de précision :

* la **catégorie**, portée par la classe (``DATA_VALIDATION_ERROR``…), dit quelle
  famille de problème s'est produite ;
* le **code**, porté par l'instance (``BINARY_VALIDATION_FAILED``…), dit
  exactement lequel.

Structure inspirée du moteur statistique d'ExperimentOS.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ABStatsError",
    "DataValidationError",
    "InsufficientSampleError",
    "InvalidParameterError",
    "InternalConsistencyError",
]


class ABStatsError(Exception):
    """Classe de base de toutes les erreurs levées par ``ab_stats``."""

    category = "AB_STATS_ERROR"

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        """Représentation compatible JSON."""
        return {
            "code": self.code,
            "category": self.category,
            "message": self.message,
            "details": dict(self.details),
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class DataValidationError(ABStatsError):
    """Les données ne correspondent pas à ce qui a été déclaré.

    Exemple : métrique déclarée binaire contenant la valeur ``2``. Le problème
    ne peut pas être corrigé sans deviner une intention : l'analyste doit
    trancher.
    """

    category = "DATA_VALIDATION_ERROR"


class InsufficientSampleError(ABStatsError):
    """Il ne reste pas assez d'observations exploitables pour analyser."""

    category = "INSUFFICIENT_SAMPLE_ERROR"


class InvalidParameterError(ABStatsError, ValueError):
    """Une déclaration ou un paramètre est incohérent en lui-même.

    Hérite aussi de ``ValueError`` : c'est une valeur d'argument invalide, et le
    code appelant peut l'intercepter comme telle.
    """

    category = "INVALID_PARAMETER_ERROR"


class InternalConsistencyError(ABStatsError):
    """Incohérence qui révèle un bug de notre code, pas un problème de données.

    Exemple : deux colonnes extraites d'un même fichier CSV n'ont pas la même
    longueur. C'est impossible si le fichier a été lu correctement ; si ça
    arrive, c'est le parseur ou le frontend qui est en cause, pas l'utilisateur.
    """

    category = "INTERNAL_CONSISTENCY_ERROR"
