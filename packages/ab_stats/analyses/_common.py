"""Briques partagées par les sept méthodes d'analyse.

Ce module ne calcule aucune statistique. Il regroupe ce que chaque méthode
ferait sinon à sa façon :

* la validation des paramètres (``alpha``, niveau de confiance, graine,
  nombre de rééchantillonnages) ;
* la traduction de l'hypothèse alternative vers le vocabulaire de SciPy et de
  statsmodels ;
* les métadonnées de reproductibilité (empreinte des données, versions des
  bibliothèques).

Le piège principal est la traduction de l'alternative. Les trois vocabulaires
diffèrent, et statsmodels compare toujours son **premier** argument au second :
pour respecter la convention B − A, B doit être passé en premier. Une erreur
d'ordre ne plante pas — elle inverse silencieusement le sens de ``greater``.
C'est pourquoi la traduction est écrite une seule fois, ici.

Structure inspirée du module ``analyses/_common`` d'ExperimentOS.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from importlib import metadata
from typing import Any

import numpy as np

from ab_stats.exceptions import InvalidParameterError
from ab_stats.results import Alternative, Reproducibility

__all__ = [
    "MIN_RESAMPLES",
    "MAX_RESAMPLES",
    "TRACKED_LIBRARIES",
    "validate_alpha",
    "validate_confidence_level",
    "validate_seed",
    "validate_n_resamples",
    "normalize_alternative",
    "to_scipy_alternative",
    "to_statsmodels_alternative",
    "compute_input_hash",
    "library_versions",
    "build_reproducibility",
]


#: Bornes du nombre de rééchantillonnages (permutation, bootstrap). En dessous
#: de 100, la p-value empirique est trop grossière ; au-delà de 100 000, le
#: temps de calcul devient déraisonnable pour une application interactive.
MIN_RESAMPLES = 100
MAX_RESAMPLES = 100_000

#: Bibliothèques dont la version est enregistrée dans chaque résultat.
TRACKED_LIBRARIES = ("ab_stats", "numpy", "scipy", "statsmodels")

_PARAMETER_ERROR = "INVALID_ANALYSIS_PARAMETER"

_SCIPY_ALTERNATIVES = {
    Alternative.TWO_SIDED: "two-sided",
    Alternative.GREATER: "greater",
    Alternative.LESS: "less",
}

# statsmodels dit « larger » / « smaller », et refuse « greater » / « less ».
_STATSMODELS_ALTERNATIVES = {
    Alternative.TWO_SIDED: "two-sided",
    Alternative.GREATER: "larger",
    Alternative.LESS: "smaller",
}


# ---------------------------------------------------------------------------
# Validation des paramètres
# ---------------------------------------------------------------------------


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _open_unit_interval(value: Any, parameter: str) -> None:
    if not _is_number(value) or not 0.0 < value < 1.0:
        raise InvalidParameterError(
            _PARAMETER_ERROR,
            "Ce paramètre doit être un nombre strictement compris entre 0 et 1.",
            details={"parameter": parameter, "value": value},
        )


def validate_alpha(alpha: float) -> None:
    """Seuil de signification, strictement dans ]0, 1[."""
    _open_unit_interval(alpha, "alpha")


def validate_confidence_level(level: float) -> None:
    """Niveau de l'intervalle de confiance, strictement dans ]0, 1[."""
    _open_unit_interval(level, "confidence_level")


def validate_seed(seed: int) -> None:
    """Graine aléatoire : entier positif ou nul, **obligatoire**.

    ``None`` est refusé : sans graine explicite, deux exécutions sur les mêmes
    données donneraient des résultats différents, et la promesse de
    reproductibilité du contrat serait fausse.
    """
    if seed is None:
        raise InvalidParameterError(
            _PARAMETER_ERROR,
            "Une graine explicite est obligatoire pour les méthodes de "
            "rééchantillonnage : sans elle, le résultat n'est pas reproductible.",
            details={"parameter": "seed", "value": None},
        )
    if not _is_integer(seed) or seed < 0:
        raise InvalidParameterError(
            _PARAMETER_ERROR,
            "La graine doit être un entier positif ou nul.",
            details={"parameter": "seed", "value": seed},
        )


def validate_n_resamples(n_resamples: int) -> None:
    """Nombre de rééchantillonnages, entier entre les bornes déclarées."""
    if not _is_integer(n_resamples) or not MIN_RESAMPLES <= n_resamples <= MAX_RESAMPLES:
        raise InvalidParameterError(
            _PARAMETER_ERROR,
            f"Le nombre de rééchantillonnages doit être un entier entre "
            f"{MIN_RESAMPLES} et {MAX_RESAMPLES}.",
            details={
                "parameter": "n_resamples",
                "value": n_resamples,
                "minimum": MIN_RESAMPLES,
                "maximum": MAX_RESAMPLES,
            },
        )


# ---------------------------------------------------------------------------
# Hypothèse alternative
# ---------------------------------------------------------------------------


def normalize_alternative(alternative: Alternative | str) -> Alternative:
    """Accepte l'énumération ou sa valeur texte (``"greater"``…)."""
    try:
        return Alternative(alternative)
    except ValueError:
        raise InvalidParameterError(
            _PARAMETER_ERROR,
            "Hypothèse alternative inconnue.",
            details={
                "parameter": "alternative",
                "value": str(alternative),
                "allowed": [a.value for a in Alternative],
            },
        ) from None


def to_scipy_alternative(alternative: Alternative | str) -> str:
    """Vocabulaire SciPy. L'appelant passe B en premier argument."""
    return _SCIPY_ALTERNATIVES[normalize_alternative(alternative)]


def to_statsmodels_alternative(alternative: Alternative | str) -> str:
    """Vocabulaire statsmodels. L'appelant passe B en premier argument."""
    return _STATSMODELS_ALTERNATIVES[normalize_alternative(alternative)]


# ---------------------------------------------------------------------------
# Reproductibilité
# ---------------------------------------------------------------------------


def _canonical_bytes(values: Any) -> bytes:
    """Représentation binaire stable d'un échantillon.

    ``float64`` petit-boutiste explicite, pour que l'empreinte soit la même sur
    toutes les machines. ``+ 0.0`` ramène ``-0.0`` à ``0.0`` : les deux valeurs
    sont égales mais n'ont pas les mêmes octets.
    """
    array = np.asarray(values, dtype=np.float64) + 0.0
    return array.astype("<f8").tobytes()


def compute_input_hash(group_a: Any, group_b: Any) -> str:
    """Empreinte SHA-256 des données réellement analysées.

    Calculée sur les valeurs normalisées, pas sur le fichier CSV : deux fichiers
    différents qui conduisent aux mêmes données retenues ont la même empreinte.

    Les effectifs sont inclus en tête. Sans eux, A = [1, 2], B = [3] et
    A = [1], B = [2, 3] produiraient les mêmes octets une fois concaténés.
    """
    bytes_a = _canonical_bytes(group_a)
    bytes_b = _canonical_bytes(group_b)
    digest = hashlib.sha256()
    digest.update(np.array([len(bytes_a) // 8, len(bytes_b) // 8], dtype="<i8").tobytes())
    digest.update(bytes_a)
    digest.update(bytes_b)
    return f"sha256:{digest.hexdigest()}"


def library_versions() -> dict[str, str]:
    """Versions installées des bibliothèques qui participent au calcul."""
    versions = {}
    for name in TRACKED_LIBRARIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "non installé"
    return versions


def build_reproducibility(
    group_a: Any,
    group_b: Any,
    *,
    seed: int | None = None,
    n_resamples: int | None = None,
    computed_at: datetime | None = None,
) -> Reproducibility:
    """Assemble les métadonnées de reproductibilité d'un résultat.

    ``computed_at`` n'est paramétrable que pour les tests ; par défaut, c'est
    l'instant présent en UTC.
    """
    return Reproducibility(
        computed_at=computed_at or datetime.now(timezone.utc),
        input_hash=compute_input_hash(group_a, group_b),
        library_versions=library_versions(),
        seed=seed,
        n_resamples=n_resamples,
    )
