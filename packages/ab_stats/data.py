"""Validation et normalisation d'un jeu de données A/B.

Le module reçoit **deux colonnes de valeurs brutes** — le groupe et la métrique —
déjà extraites d'un fichier. Il ne lit aucun fichier : le parsing CSV
(délimiteur, encodage, en-têtes, taille maximale en octets) appartient au
backend.

Il suit le flux de l'étape Dataset :

1. :func:`profile_group_column` et :func:`profile_metric_column` décrivent les
   colonnes **avant** toute déclaration : valeurs trouvées, décomptes, type de
   métrique proposé et les preuves de cette proposition.
2. L'analyste déclare le mapping A/B (:class:`GroupMapping`) et le type de
   métrique (:class:`MetricDeclaration`).
3. :func:`normalize` vérifie les données **contre la déclaration** et produit un
   :class:`NormalizedDataset` accompagné de son :class:`ValidationReport`.

Règle générale : on écarte ce qui est inutilisable en le comptant, on normalise
un simple format en le déclarant, et on s'arrête dès qu'il faudrait deviner une
intention. Aucune valeur n'est jamais inventée, aucun groupe n'est jamais
fusionné en silence.

Conventions de lecture des valeurs :

* seules les cellules **vides** (``None``, ``NaN``, chaîne blanche) sont des
  valeurs manquantes ; ``"n/a"`` est une valeur non numérique ;
* l'identité d'une valeur de groupe ou d'un codage binaire est **exacte** :
  ``"control"``, ``"Control"`` et ``"control "`` sont trois valeurs distinctes,
  signalées comme ressemblantes mais jamais fusionnées ;
* un nombre, lui, est lu sans tenir compte des espaces qui l'entourent.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from ab_stats.exceptions import (
    DataValidationError,
    InsufficientSampleError,
    InternalConsistencyError,
    InvalidParameterError,
)
from ab_stats.results import (
    UNIT_PROPORTION,
    AnalysisWarning,
    Method,
    MetricType,
    Severity,
)

__all__ = [
    "DEFAULT_HIGH_EXCLUSION_RATE",
    "ProposedMetricType",
    "DecimalSeparator",
    "DecimalAmbiguity",
    "ExclusionReason",
    "ValueCount",
    "SimilarValues",
    "GroupColumnProfile",
    "MetricColumnProfile",
    "GroupMapping",
    "BinaryEncoding",
    "MetricDeclaration",
    "ExclusionSummary",
    "ValidationReport",
    "NormalizedDataset",
    "profile_group_column",
    "profile_metric_column",
    "normalize",
]


#: Au-delà de cette part de lignes écartées, un avertissement est émis.
DEFAULT_HIGH_EXCLUSION_RATE = 0.10

#: Nombre maximal de valeurs listées dans un profil de métrique ou une erreur.
MAX_LISTED_VALUES = 10

#: Nombre maximal de valeurs listées dans un profil de colonne groupe.
MAX_LISTED_GROUP_VALUES = 50

#: Nombre d'indices de lignes donnés en exemple pour chaque problème.
MAX_SAMPLE_ROWS = 5

_POINT_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_COMMA_DECIMAL = re.compile(r"[+-]?\d+,\d+")
_INTEGER = re.compile(r"[+-]?\d+")
_THOUSANDS_LIKE = re.compile(r"[+-]?\d{1,3},\d{3}")


# ---------------------------------------------------------------------------
# Énumérations
# ---------------------------------------------------------------------------


class ProposedMetricType(str, Enum):
    """Type de métrique **proposé** par la détection, avant confirmation."""

    BINARY = "binary"
    """Valeurs contenues dans ``{0, 1}`` : utilisable directement."""

    BINARY_ENCODABLE = "binary_encodable"
    """Deux valeurs qui ne sont pas ``{0, 1}`` (``yes``/``no``) : codage à déclarer."""

    CONTINUOUS = "continuous"
    """Valeurs numériques variées."""

    UNSUPPORTED = "unsupported"
    """Texte à plus de deux valeurs, ou colonne vide : non analysable."""


class DecimalSeparator(str, Enum):
    """Séparateur décimal d'une colonne. Une colonne n'en a qu'un."""

    POINT = "."
    COMMA = ","


class DecimalAmbiguity(str, Enum):
    """Raison pour laquelle le séparateur décimal ne peut pas être deviné."""

    MIXED_SEPARATORS = "mixed_separators"
    """Des points et des virgules décimales cohabitent dans la colonne."""

    POSSIBLE_THOUSANDS_SEPARATOR = "possible_thousands_separator"
    """Toutes les virgules sont suivies de trois chiffres (``1,234``)."""


class ExclusionReason(str, Enum):
    """Motif d'exclusion d'une ligne, dans l'ordre de priorité d'examen.

    Une ligne n'est exclue que pour un seul motif : le premier rencontré.
    """

    MISSING_GROUP = "MISSING_GROUP"
    UNMAPPED_GROUP_VALUE = "UNMAPPED_GROUP_VALUE"
    MISSING_METRIC = "MISSING_METRIC"
    NON_NUMERIC_METRIC = "NON_NUMERIC_METRIC"


# ---------------------------------------------------------------------------
# Profils (avant déclaration)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValueCount:
    """Une valeur exacte et son nombre d'occurrences."""

    value: str
    count: int


@dataclass(frozen=True, slots=True)
class SimilarValues:
    """Valeurs distinctes qui ne diffèrent que par la casse ou les espaces.

    Signalées pour que l'analyste puisse corriger son fichier ; jamais
    fusionnées automatiquement.
    """

    key: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GroupColumnProfile:
    """Ce que contient la colonne groupe, pour préparer le mapping A/B."""

    n_rows: int
    n_missing: int
    n_distinct: int
    values: tuple[ValueCount, ...]
    similar_values: tuple[SimilarValues, ...]

    @property
    def is_truncated(self) -> bool:
        """Vrai si toutes les valeurs distinctes ne sont pas listées."""
        return len(self.values) < self.n_distinct


@dataclass(frozen=True, slots=True)
class MetricColumnProfile:
    """Type de métrique proposé **et les preuves** de cette proposition.

    La proposition n'est jamais appliquée seule : elle est affichée pour que
    l'analyste la confirme ou la corrige.
    """

    n_rows: int
    n_missing: int
    n_distinct: int
    proposed_type: ProposedMetricType
    top_values: tuple[ValueCount, ...]
    n_non_numeric: int
    non_numeric_examples: tuple[str, ...]
    decimal_separator: DecimalSeparator | None
    decimal_ambiguity: DecimalAmbiguity | None
    n_comma_decimal_values: int


# ---------------------------------------------------------------------------
# Déclarations de l'analyste
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GroupMapping:
    """Quelle valeur de la colonne groupe désigne A, laquelle désigne B.

    A est le contrôle (la référence), B le traitement (la nouveauté). L'effet
    étant toujours calculé en B − A, inverser ce mapping inverse la conclusion.
    """

    a: str
    b: str

    def __post_init__(self) -> None:
        for field_name in ("a", "b"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidParameterError(
                    "GROUP_MAPPING_INCOMPLETE",
                    f"La valeur du groupe {field_name.upper()} doit être une chaîne non vide.",
                    details={"field": field_name},
                )
        if self.a == self.b:
            raise InvalidParameterError(
                "GROUP_MAPPING_INCOMPLETE",
                "A et B doivent désigner deux valeurs différentes.",
                details={"a": self.a, "b": self.b},
            )


@dataclass(frozen=True, slots=True)
class BinaryEncoding:
    """Codage déclaré d'une métrique binaire écrite autrement que 0/1.

    La correspondance est exacte : si ``success = "yes"``, la valeur ``"YES"``
    n'est pas reconnue et bloque la validation.
    """

    success: str
    failure: str

    def __post_init__(self) -> None:
        for field_name in ("success", "failure"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidParameterError(
                    "BINARY_MAPPING_INVALID",
                    f"La valeur « {field_name} » du codage binaire doit être non vide.",
                    details={"field": field_name},
                )
        if self.success == self.failure:
            raise InvalidParameterError(
                "BINARY_MAPPING_INVALID",
                "Les valeurs de succès et d'échec doivent être différentes.",
                details={"success": self.success, "failure": self.failure},
            )


@dataclass(frozen=True, slots=True)
class MetricDeclaration:
    """Type de métrique confirmé par l'analyste, et comment le lire.

    * Binaire sans codage : les valeurs doivent valoir numériquement 0 ou 1.
    * Binaire avec codage : les valeurs doivent être exactement ``success`` ou
      ``failure``.
    * Continue : l'unité est obligatoire (``"euros"``, ``"seconds"``…).
    """

    metric_type: MetricType
    unit: str | None = None
    binary_encoding: BinaryEncoding | None = None
    decimal_separator: DecimalSeparator = DecimalSeparator.POINT

    def __post_init__(self) -> None:
        if not isinstance(self.metric_type, MetricType):
            raise InvalidParameterError(
                "METRIC_DECLARATION_INVALID",
                "Le type de métrique doit être binary ou continuous.",
                details={"metric_type": str(self.metric_type)},
            )
        if not isinstance(self.decimal_separator, DecimalSeparator):
            raise InvalidParameterError(
                "METRIC_DECLARATION_INVALID",
                "Le séparateur décimal doit être « . » ou « , ».",
                details={"decimal_separator": str(self.decimal_separator)},
            )

        if self.metric_type is MetricType.BINARY:
            if self.unit is None:
                object.__setattr__(self, "unit", UNIT_PROPORTION)
            elif self.unit != UNIT_PROPORTION:
                raise InvalidParameterError(
                    "METRIC_DECLARATION_INVALID",
                    f"Une métrique binaire s'exprime en « {UNIT_PROPORTION} ».",
                    details={"unit": self.unit},
                )
            return

        if self.binary_encoding is not None:
            raise InvalidParameterError(
                "METRIC_DECLARATION_INVALID",
                "Un codage binaire n'a pas de sens pour une métrique continue.",
            )
        if self.unit is None or not self.unit.strip() or self.unit == UNIT_PROPORTION:
            raise InvalidParameterError(
                "METRIC_DECLARATION_INVALID",
                "Une métrique continue exige son unité (« euros », « seconds »…).",
                details={"unit": self.unit},
            )


# ---------------------------------------------------------------------------
# Sortie normalisée
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExclusionSummary:
    """Toutes les lignes écartées pour un même motif."""

    reason: ExclusionReason
    count: int
    sample_row_indices: tuple[int, ...]
    values: tuple[ValueCount, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Le reçu de la normalisation : ce qui a été gardé, écarté et converti.

    Les indices de lignes commencent à 0 à la première ligne de **données**
    (la ligne d'en-tête n'est pas comptée).
    """

    n_input: int
    n_retained: int
    exclusions: tuple[ExclusionSummary, ...]
    group_mapping: GroupMapping
    metric_declaration: MetricDeclaration
    decimal_conversions: int
    warnings: tuple[AnalysisWarning, ...]
    group_column_name: str
    metric_column_name: str

    def __post_init__(self) -> None:
        if self.n_retained + self.n_excluded != self.n_input:
            raise InternalConsistencyError(
                "REPORT_COUNT_MISMATCH",
                "Erreur interne : lignes retenues et exclues ne totalisent pas l'entrée.",
                details={
                    "n_input": self.n_input,
                    "n_retained": self.n_retained,
                    "n_excluded": self.n_excluded,
                },
            )

    @property
    def n_excluded(self) -> int:
        """Nombre total de lignes écartées."""
        return sum(summary.count for summary in self.exclusions)

    @property
    def exclusion_rate(self) -> float:
        """Part des lignes écartées."""
        return self.n_excluded / self.n_input

    def excluded(self, reason: ExclusionReason) -> int:
        """Nombre de lignes écartées pour un motif donné."""
        return sum(s.count for s in self.exclusions if s.reason is reason)


@dataclass(frozen=True, slots=True, eq=False)
class NormalizedDataset:
    """Les deux échantillons prêts pour l'analyse, et leur rapport.

    Les tableaux sont en lecture seule : ils ne peuvent pas être modifiés après
    la validation. ``eq=False`` car comparer deux objets contenant des
    tableaux NumPy n'a pas de sens booléen unique.
    """

    group_a: np.ndarray
    group_b: np.ndarray
    metric_type: MetricType
    unit: str
    report: ValidationReport

    @property
    def n_a(self) -> int:
        """Effectif retenu du groupe A."""
        return int(self.group_a.size)

    @property
    def n_b(self) -> int:
        """Effectif retenu du groupe B."""
        return int(self.group_b.size)


# ---------------------------------------------------------------------------
# Lecture des valeurs
# ---------------------------------------------------------------------------


def _as_column(values: Iterable[Any], *, name: str) -> list[Any]:
    """Convertit une colonne (liste, tuple, tableau NumPy, Series) en liste."""
    if isinstance(values, (str, bytes)):
        raise InvalidParameterError(
            "INVALID_COLUMN",
            "Une colonne doit être une séquence de valeurs, pas une chaîne.",
            details={"column": name},
        )
    if isinstance(values, np.ndarray):
        if values.ndim != 1:
            raise InvalidParameterError(
                "INVALID_COLUMN",
                "Une colonne doit être unidimensionnelle.",
                details={"column": name, "dimensions": int(values.ndim)},
            )
        return values.tolist()
    try:
        return list(values)
    except TypeError as error:
        raise InvalidParameterError(
            "INVALID_COLUMN",
            "Une colonne doit être une séquence de valeurs.",
            details={"column": name},
        ) from error


def _to_token(value: Any) -> str | None:
    """Représentation textuelle exacte d'une cellule, ou ``None`` si vide."""
    if value is None or type(value).__name__ in {"NAType", "NaTType"}:
        return None
    if isinstance(value, (bool, np.bool_)):
        return "true" if value else "false"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if math.isnan(number):
            return None
        if math.isinf(number):
            return "inf" if number > 0 else "-inf"
        return str(int(number)) if number.is_integer() else format(number, ".15g")
    text = value if isinstance(value, str) else str(value)
    return text if text.strip() else None


def _similarity_key(token: str) -> str:
    """Clé de ressemblance : sans espaces externes ni casse."""
    return token.strip().casefold()


def _numeric_value_any(token: str) -> float | None:
    """Valeur numérique finie d'un jeton, quel que soit son séparateur décimal."""
    text = token.strip()
    if _POINT_NUMBER.fullmatch(text):
        number = float(text)
    elif _COMMA_DECIMAL.fullmatch(text):
        number = float(text.replace(",", "."))
    else:
        return None
    return number if math.isfinite(number) else None


def _parse_number(token: str, separator: DecimalSeparator) -> float | None:
    """Valeur numérique finie d'un jeton lu avec le séparateur déclaré."""
    text = token.strip()
    if separator is DecimalSeparator.COMMA:
        if _COMMA_DECIMAL.fullmatch(text):
            text = text.replace(",", ".")
        elif not _INTEGER.fullmatch(text):
            return None
    elif not _POINT_NUMBER.fullmatch(text):
        return None
    number = float(text)
    return number if math.isfinite(number) else None


def _separator_mismatch(token: str, separator: DecimalSeparator) -> bool:
    """Vrai si le jeton est un nombre écrit avec l'**autre** séparateur."""
    text = token.strip()
    if separator is DecimalSeparator.POINT:
        return bool(_COMMA_DECIMAL.fullmatch(text))
    return (
        "." in text
        and bool(_POINT_NUMBER.fullmatch(text))
        and not _INTEGER.fullmatch(text)
    )


def _ordered_counts(tokens: list[str | None]) -> list[ValueCount]:
    """Décomptes par ordre décroissant, puis par ordre d'apparition."""
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if token is None:
            continue
        counts[token] += 1
        first_seen.setdefault(token, index)
    ordered = sorted(counts, key=lambda token: (-counts[token], first_seen[token]))
    return [ValueCount(token, counts[token]) for token in ordered]


def _counter_to_values(counter: Counter[str], limit: int) -> tuple[ValueCount, ...]:
    """Les valeurs les plus fréquentes d'un compteur."""
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return tuple(ValueCount(value, count) for value, count in ordered[:limit])


def _values_payload(values: Iterable[ValueCount]) -> list[dict[str, Any]]:
    """Représentation JSON d'une liste de décomptes."""
    return [{"value": item.value, "count": item.count} for item in values]


# ---------------------------------------------------------------------------
# Profilage
# ---------------------------------------------------------------------------


def profile_group_column(
    values: Iterable[Any],
    *,
    max_listed: int = MAX_LISTED_GROUP_VALUES,
) -> GroupColumnProfile:
    """Décrit la colonne groupe pour que l'analyste puisse choisir A et B.

    Liste les valeurs exactes avec leurs décomptes et repère celles qui ne
    diffèrent que par la casse ou les espaces.
    """
    tokens = [_to_token(value) for value in _as_column(values, name="group")]
    ordered = _ordered_counts(tokens)

    by_key: dict[str, list[str]] = {}
    for item in ordered:
        by_key.setdefault(_similarity_key(item.value), []).append(item.value)
    similar = tuple(
        SimilarValues(key=key, values=tuple(variants))
        for key, variants in by_key.items()
        if len(variants) > 1
    )

    return GroupColumnProfile(
        n_rows=len(tokens),
        n_missing=tokens.count(None),
        n_distinct=len(ordered),
        values=tuple(ordered[:max_listed]),
        similar_values=similar,
    )


def profile_metric_column(
    values: Iterable[Any],
    *,
    max_listed: int = MAX_LISTED_VALUES,
) -> MetricColumnProfile:
    """Propose un type de métrique et expose les preuves de la proposition.

    Détecte aussi le séparateur décimal de la colonne, et refuse de le deviner
    quand la colonne est ambiguë.
    """
    tokens = [_to_token(value) for value in _as_column(values, name="metric")]
    ordered = _ordered_counts(tokens)
    counts = {item.value: item.count for item in ordered}
    distinct = list(counts)

    comma_tokens = [t for t in distinct if _COMMA_DECIMAL.fullmatch(t.strip())]
    point_decimal_tokens = [
        t
        for t in distinct
        if _POINT_NUMBER.fullmatch(t.strip()) and not _INTEGER.fullmatch(t.strip())
    ]

    decimal_separator: DecimalSeparator | None
    decimal_ambiguity: DecimalAmbiguity | None = None
    if comma_tokens and point_decimal_tokens:
        decimal_separator = None
        decimal_ambiguity = DecimalAmbiguity.MIXED_SEPARATORS
    elif comma_tokens:
        decimal_separator = DecimalSeparator.COMMA
        if all(_THOUSANDS_LIKE.fullmatch(t.strip()) for t in comma_tokens):
            decimal_ambiguity = DecimalAmbiguity.POSSIBLE_THOUSANDS_SEPARATOR
    else:
        decimal_separator = DecimalSeparator.POINT

    numeric_values = {
        number
        for number in (_numeric_value_any(token) for token in distinct)
        if number is not None
    }
    non_numeric = [token for token in distinct if _numeric_value_any(token) is None]

    return MetricColumnProfile(
        n_rows=len(tokens),
        n_missing=tokens.count(None),
        n_distinct=len(distinct),
        proposed_type=_propose_metric_type(numeric_values, non_numeric, len(distinct)),
        top_values=tuple(ordered[:max_listed]),
        n_non_numeric=sum(counts[token] for token in non_numeric),
        non_numeric_examples=tuple(non_numeric[:MAX_SAMPLE_ROWS]),
        decimal_separator=decimal_separator,
        decimal_ambiguity=decimal_ambiguity,
        n_comma_decimal_values=sum(counts[token] for token in comma_tokens),
    )


def _propose_metric_type(
    numeric_values: set[float],
    non_numeric: list[str],
    n_distinct: int,
) -> ProposedMetricType:
    """Règle de proposition du type de métrique."""
    if n_distinct == 0:
        return ProposedMetricType.UNSUPPORTED

    if not non_numeric:
        if numeric_values <= {0.0, 1.0}:
            return ProposedMetricType.BINARY
        if n_distinct == 2:
            return ProposedMetricType.BINARY_ENCODABLE
        return ProposedMetricType.CONTINUOUS

    # Quelques valeurs parasites (« n/a ») au milieu de nombres variés :
    # la colonne reste continue, les parasites seront écartés et comptés.
    if len(numeric_values) >= 3:
        return ProposedMetricType.CONTINUOUS
    if n_distinct <= 2:
        return ProposedMetricType.BINARY_ENCODABLE
    if numeric_values and numeric_values <= {0.0, 1.0}:
        return ProposedMetricType.BINARY
    return ProposedMetricType.UNSUPPORTED


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


class _Tally:
    """Compteur d'une catégorie de lignes : total, exemples et valeurs."""

    __slots__ = ("count", "rows", "values")

    def __init__(self) -> None:
        self.count = 0
        self.rows: list[int] = []
        self.values: Counter[str] = Counter()

    def add(self, index: int, value: str | None = None) -> None:
        self.count += 1
        if len(self.rows) < MAX_SAMPLE_ROWS:
            self.rows.append(index)
        if value is not None:
            self.values[value] += 1


def normalize(
    group_values: Iterable[Any],
    metric_values: Iterable[Any],
    *,
    mapping: GroupMapping,
    declaration: MetricDeclaration,
    exclude_unmapped_groups: bool = False,
    group_column_name: str = "group",
    metric_column_name: str = "metric",
    high_exclusion_rate: float = DEFAULT_HIGH_EXCLUSION_RATE,
) -> NormalizedDataset:
    """Valide les deux colonnes contre les déclarations de l'analyste.

    Ordre des vérifications :

    1. cohérence structurelle (colonnes de même longueur, jeu non vide) ;
    2. mapping : A et B existent ; les autres valeurs de groupe ne sont
       écartées que si ``exclude_unmapped_groups`` confirme l'exclusion ;
    3. parcours ligne par ligne et exclusions, un seul motif par ligne ;
    4. validation du type déclaré, **sur les lignes non exclues seulement** ;
    5. vérification qu'il reste des observations dans A et dans B ;
    6. avertissements informatifs ;
    7. construction de la sortie en lecture seule.

    Raises:
        InternalConsistencyError: colonnes de longueurs différentes.
        DataValidationError: les données contredisent la déclaration.
        InsufficientSampleError: il ne reste rien à analyser.
        InvalidParameterError: paramètre incohérent.
    """
    if not 0.0 < high_exclusion_rate <= 1.0:
        raise InvalidParameterError(
            "INVALID_PARAMETER",
            "high_exclusion_rate doit être dans ]0, 1].",
            details={"high_exclusion_rate": high_exclusion_rate},
        )

    # 1. Cohérence structurelle -------------------------------------------------
    group_tokens = [_to_token(v) for v in _as_column(group_values, name=group_column_name)]
    metric_raw = _as_column(metric_values, name=metric_column_name)

    if len(group_tokens) != len(metric_raw):
        raise InternalConsistencyError(
            "COLUMN_LENGTH_MISMATCH",
            "Erreur interne : les colonnes extraites n'ont pas la même longueur.",
            details={
                "group_column": group_column_name,
                "group_length": len(group_tokens),
                "metric_column": metric_column_name,
                "metric_length": len(metric_raw),
            },
        )
    n_input = len(group_tokens)
    if n_input == 0:
        raise DataValidationError(
            "EMPTY_DATASET",
            "Le jeu de données ne contient aucune ligne.",
        )

    # 2. Mapping ----------------------------------------------------------------
    group_counts = Counter(token for token in group_tokens if token is not None)
    mapped = (mapping.a, mapping.b)

    not_found = [
        (field_name, value)
        for field_name, value in (("a", mapping.a), ("b", mapping.b))
        if value not in group_counts
    ]
    if not_found:
        raise DataValidationError(
            "GROUP_VALUE_NOT_FOUND",
            "Une valeur déclarée pour A ou B n'existe pas dans la colonne groupe.",
            details={
                "column": group_column_name,
                "missing": [
                    {
                        "field": field_name,
                        "value": value,
                        "did_you_mean": sorted(
                            token
                            for token in group_counts
                            if _similarity_key(token) == _similarity_key(value)
                        ),
                    }
                    for field_name, value in not_found
                ],
                "available_values": _values_payload(
                    _counter_to_values(group_counts, MAX_LISTED_GROUP_VALUES)
                ),
            },
        )

    unmapped = Counter({token: n for token, n in group_counts.items() if token not in mapped})
    mapped_keys = {_similarity_key(value): value for value in mapped}
    similar_to_mapped = [
        {"value": token, "resembles": mapped_keys[_similarity_key(token)]}
        for token in sorted(unmapped)
        if _similarity_key(token) in mapped_keys
    ]
    if unmapped and not exclude_unmapped_groups:
        raise DataValidationError(
            "UNMAPPED_GROUP_VALUES",
            "La colonne groupe contient des valeurs qui ne sont ni A ni B. "
            "Confirmez leur exclusion ou corrigez le mapping.",
            details={
                "column": group_column_name,
                "mapped": {"a": mapping.a, "b": mapping.b},
                "unmapped_values": _values_payload(
                    _counter_to_values(unmapped, MAX_LISTED_GROUP_VALUES)
                ),
                "affected_rows": sum(unmapped.values()),
                "total_rows": n_input,
                "similar_to_mapped": similar_to_mapped,
            },
        )

    # 3. Parcours ligne par ligne ------------------------------------------------
    is_binary = declaration.metric_type is MetricType.BINARY
    encoding = declaration.binary_encoding
    separator = declaration.decimal_separator

    tallies = {reason: _Tally() for reason in ExclusionReason}
    invalid_binary = _Tally()
    separator_mismatch = _Tally()
    retained_a: list[float] = []
    retained_b: list[float] = []
    decimal_conversions = 0

    for index, (group_token, raw_metric) in enumerate(zip(group_tokens, metric_raw)):
        if group_token is None:
            tallies[ExclusionReason.MISSING_GROUP].add(index)
            continue
        if group_token not in mapped:
            tallies[ExclusionReason.UNMAPPED_GROUP_VALUE].add(index, group_token)
            continue

        metric_token = _to_token(raw_metric)
        if metric_token is None:
            tallies[ExclusionReason.MISSING_METRIC].add(index)
            continue

        if is_binary:
            value = _binary_value(metric_token, encoding)
            if value is None:
                invalid_binary.add(index, metric_token)
                continue
        else:
            if isinstance(raw_metric, (bool, np.bool_)):
                tallies[ExclusionReason.NON_NUMERIC_METRIC].add(index, metric_token)
                continue
            if _separator_mismatch(metric_token, separator):
                separator_mismatch.add(index, metric_token)
                continue
            value = _parse_number(metric_token, separator)
            if value is None:
                tallies[ExclusionReason.NON_NUMERIC_METRIC].add(index, metric_token)
                continue
            if separator is DecimalSeparator.COMMA and "," in metric_token:
                decimal_conversions += 1

        (retained_a if group_token == mapping.a else retained_b).append(value)

    # 4. Validation du type déclaré (lignes non exclues seulement) -------------
    if invalid_binary.count:
        _raise_invalid_binary(
            invalid_binary,
            encoding=encoding,
            n_candidates=len(retained_a) + len(retained_b) + invalid_binary.count,
            metric_column_name=metric_column_name,
        )
    if separator_mismatch.count:
        raise DataValidationError(
            "DECIMAL_SEPARATOR_MISMATCH",
            "Des nombres utilisent un autre séparateur décimal que celui déclaré.",
            details={
                "column": metric_column_name,
                "declared_separator": separator.value,
                "examples": _values_payload(
                    _counter_to_values(separator_mismatch.values, MAX_LISTED_VALUES)
                ),
                "affected_rows": separator_mismatch.count,
                "sample_row_indices": list(separator_mismatch.rows),
            },
        )

    # 5. Il reste des observations ---------------------------------------------
    exclusion_counts = {
        reason.value: tally.count for reason, tally in tallies.items() if tally.count
    }
    if not retained_a and not retained_b:
        raise InsufficientSampleError(
            "ALL_ROWS_EXCLUDED",
            "Aucune ligne exploitable ne reste après les exclusions.",
            details={"n_input": n_input, "exclusions": exclusion_counts},
        )
    empty_groups = [
        field_name
        for field_name, values in (("a", retained_a), ("b", retained_b))
        if not values
    ]
    if empty_groups:
        raise InsufficientSampleError(
            "EMPTY_GROUP",
            "Un des deux groupes ne conserve aucune observation après les exclusions.",
            details={
                "empty_groups": empty_groups,
                "mapped": {"a": mapping.a, "b": mapping.b},
                "retained": {"a": len(retained_a), "b": len(retained_b)},
                "exclusions": exclusion_counts,
            },
        )

    # 6. Avertissements ----------------------------------------------------------
    exclusions = tuple(
        ExclusionSummary(
            reason=reason,
            count=tally.count,
            sample_row_indices=tuple(tally.rows),
            values=_counter_to_values(tally.values, MAX_LISTED_VALUES),
        )
        for reason, tally in tallies.items()
        if tally.count
    )
    n_retained = len(retained_a) + len(retained_b)
    warnings = _build_warnings(
        retained_a=retained_a,
        retained_b=retained_b,
        declaration=declaration,
        n_input=n_input,
        n_excluded=n_input - n_retained,
        high_exclusion_rate=high_exclusion_rate,
        similar_to_mapped=similar_to_mapped,
    )

    # 7. Sortie ------------------------------------------------------------------
    report = ValidationReport(
        n_input=n_input,
        n_retained=n_retained,
        exclusions=exclusions,
        group_mapping=mapping,
        metric_declaration=declaration,
        decimal_conversions=decimal_conversions,
        warnings=warnings,
        group_column_name=group_column_name,
        metric_column_name=metric_column_name,
    )
    return NormalizedDataset(
        group_a=_read_only(retained_a),
        group_b=_read_only(retained_b),
        metric_type=declaration.metric_type,
        unit=declaration.unit or UNIT_PROPORTION,
        report=report,
    )


def _binary_value(token: str, encoding: BinaryEncoding | None) -> float | None:
    """Valeur 0/1 d'un jeton binaire, ou ``None`` s'il n'est pas reconnu.

    Sans codage déclaré, la comparaison est numérique (``"1"``, ``"1.0"`` et
    ``1`` valent 1). Avec un codage déclaré, elle est exacte.
    """
    if encoding is None:
        number = _numeric_value_any(token)
        if number == 1.0:
            return 1.0
        if number == 0.0:
            return 0.0
        return None
    if token == encoding.success:
        return 1.0
    if token == encoding.failure:
        return 0.0
    return None


def _raise_invalid_binary(
    tally: _Tally,
    *,
    encoding: BinaryEncoding | None,
    n_candidates: int,
    metric_column_name: str,
) -> None:
    """Lève l'erreur bloquante d'une métrique binaire non conforme."""
    if encoding is None:
        code = "BINARY_VALIDATION_FAILED"
        message = "La métrique est déclarée binaire mais contient d'autres valeurs que 0 et 1."
        expected = ["0", "1"]
    else:
        code = "BINARY_ENCODING_INCOMPLETE"
        message = "Le codage binaire déclaré ne couvre pas toutes les valeurs présentes."
        expected = [encoding.failure, encoding.success]

    raise DataValidationError(
        code,
        message,
        details={
            "column": metric_column_name,
            "declared_metric_type": MetricType.BINARY.value,
            "expected_values": expected,
            "unexpected_values": _values_payload(
                _counter_to_values(tally.values, MAX_LISTED_VALUES)
            ),
            "n_unexpected_distinct": len(tally.values),
            "affected_rows": tally.count,
            "total_rows": n_candidates,
            "sample_row_indices": list(tally.rows),
        },
    )


def _build_warnings(
    *,
    retained_a: list[float],
    retained_b: list[float],
    declaration: MetricDeclaration,
    n_input: int,
    n_excluded: int,
    high_exclusion_rate: float,
    similar_to_mapped: list[dict[str, str]],
) -> tuple[AnalysisWarning, ...]:
    """Avertissements qui n'empêchent pas l'analyse."""
    warnings: list[AnalysisWarning] = []

    if similar_to_mapped:
        listed = ", ".join(
            f"« {item['value']} » ressemble à « {item['resembles']} »"
            for item in similar_to_mapped
        )
        warnings.append(
            AnalysisWarning(
                code="SIMILAR_GROUP_VALUES",
                severity=Severity.WARNING,
                message=f"Valeurs exclues proches d'un groupe mappé : {listed}.",
                affected_field="group",
            )
        )

    rate = n_excluded / n_input
    if rate > high_exclusion_rate:
        warnings.append(
            AnalysisWarning(
                code="HIGH_EXCLUSION_RATE",
                severity=Severity.WARNING,
                message=(
                    f"{n_excluded} lignes sur {n_input} ont été écartées "
                    f"({rate:.1%}), au-delà du seuil de {high_exclusion_rate:.0%}."
                ),
                affected_field="report",
            )
        )

    if declaration.metric_type is MetricType.CONTINUOUS:
        distinct = set(retained_a) | set(retained_b)
        if len(distinct) <= 2:
            warnings.append(
                AnalysisWarning(
                    code="CONTINUOUS_WITH_TWO_VALUES",
                    severity=Severity.WARNING,
                    message=(
                        "Métrique déclarée continue mais ne prenant que "
                        f"{len(distinct)} valeur(s) distincte(s). "
                        "Une métrique binaire est probablement plus adaptée."
                    ),
                    affected_field="metric",
                    suggested_alternative=(
                        Method.TWO_PROPORTION_Z if distinct <= {0.0, 1.0} else None
                    ),
                )
            )

    for field_name, values in (("a", retained_a), ("b", retained_b)):
        if len(set(values)) == 1:
            warnings.append(
                AnalysisWarning(
                    code="ZERO_VARIANCE",
                    severity=Severity.WARNING,
                    message=(
                        f"Le groupe {field_name.upper()} est constant "
                        f"(toutes les valeurs valent {values[0]:g})."
                    ),
                    affected_field=f"group_{field_name}",
                )
            )

    return tuple(warnings)


def _read_only(values: list[float]) -> np.ndarray:
    """Tableau NumPy immuable."""
    array = np.asarray(values, dtype=np.float64)
    array.setflags(write=False)
    return array
