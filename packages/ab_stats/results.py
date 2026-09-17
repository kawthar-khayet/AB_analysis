"""Contrat commun de résultat statistique.

Toutes les méthodes du paquet retournent un :class:`StatisticalResult`, quelle que
soit la mécanique employée pour le produire. C'est ce qui permet à la page Results,
à l'export PDF et aux types TypeScript d'être écrits une seule fois.

Ce module ne contient **aucun calcul statistique** : uniquement la structure des
données et les invariants qui la protègent.

Règles structurelles appliquées ici :

* Les objets sont immuables (``frozen=True``). Un résultat est un fait établi.
* Les collections sont des tuples, jamais des listes : une liste dans un objet
  « gelé » resterait modifiable et ruinerait la garantie.
* Le sens de l'effet est **toujours** B − A. Un signe positif signifie que le
  traitement B fait mieux que le contrôle A.
* Un intervalle de confiance ne peut pas exister sans déclarer sa méthode de
  construction, et une étiquette de taille d'effet ne peut pas exister sans
  déclarer sa convention. Le principe « never silently » est appliqué par le
  type lui-même.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

__all__ = [
    "CONTRACT_VERSION",
    "UNIT_PROPORTION",
    "EFFECT_DIRECTION",
    "MetricType",
    "Method",
    "Alternative",
    "Decision",
    "PValueSource",
    "CIMethod",
    "EstimateName",
    "EffectSizeName",
    "EffectSizeLabel",
    "AssumptionStatus",
    "Severity",
    "InterpretationCase",
    "Hypotheses",
    "GroupSummary",
    "Groups",
    "Statistic",
    "Estimate",
    "ConfidenceInterval",
    "EffectSize",
    "Assumption",
    "AnalysisWarning",
    "Reproducibility",
    "StatisticalResult",
    "Interpretation",
    "AnalysisOutcome",
]


#: Version du contrat. À incrémenter dès qu'un champ change de sens ou disparaît.
CONTRACT_VERSION = "1.0"

#: Unité conventionnelle des métriques binaires. On stocke la proportion brute
#: (0.013), jamais les points de pourcentage : c'est l'affichage qui convertit.
UNIT_PROPORTION = "proportion"

#: Sens de l'effet, constant dans tout le projet.
EFFECT_DIRECTION = "B_minus_A"


# ---------------------------------------------------------------------------
# Énumérations
# ---------------------------------------------------------------------------


class MetricType(str, Enum):
    """Nature de la métrique analysée.

    Deux types seulement : le projet ne traite pas les métriques ordinales.
    Mann-Whitney reste au catalogue, appliqué aux métriques continues à
    distribution difficile (forte asymétrie, valeurs extrêmes).
    """

    BINARY = "binary"
    CONTINUOUS = "continuous"


class Method(str, Enum):
    """Les sept méthodes du catalogue."""

    TWO_PROPORTION_Z = "two_proportion_z"
    FISHER_EXACT = "fisher_exact"
    STUDENT_T = "student_t"
    WELCH_T = "welch_t"
    MANN_WHITNEY_U = "mann_whitney_u"
    PERMUTATION = "permutation"
    BOOTSTRAP = "bootstrap"


class Alternative(str, Enum):
    """Hypothèse alternative. À fixer avant de regarder les données."""

    TWO_SIDED = "two_sided"
    GREATER = "greater"
    LESS = "less"


class Decision(str, Enum):
    """Verdict du test.

    Le vocabulaire est volontairement incomplet : ``accept_null`` et
    ``no_difference`` n'existent pas et ne doivent jamais être ajoutés. Un
    résultat non significatif signifie « preuve insuffisante », jamais
    « les groupes sont égaux ».
    """

    REJECT_NULL = "reject_null"
    FAIL_TO_REJECT_NULL = "fail_to_reject_null"
    NOT_APPLICABLE = "not_applicable"


class PValueSource(str, Enum):
    """D'où vient la p-value.

    Rendre la source obligatoire est l'application du principe « never
    silently » : le bootstrap n'a pas de p-value native, donc s'il en fournit
    une, il doit dire comment il l'a obtenue.
    """

    ANALYTIC = "analytic"
    EXACT = "exact"
    PERMUTATION = "permutation"
    BOOTSTRAP_SHIFTED = "bootstrap_shifted"


class CIMethod(str, Enum):
    """Construction employée pour l'intervalle de confiance.

    Ce champ règle deux zones grises du catalogue :

    * Fisher exact ne produit pas nativement d'IC sur la différence de taux ;
      il emprunte donc une construction déclarée (``NEWCOMBE``).
    * Le test de permutation n'a pas d'IC natif ; s'il en expose un, il déclare
      l'avoir emprunté au bootstrap (``PERCENTILE_BOOTSTRAP``).
    """

    NORMAL_APPROX_UNPOOLED = "normal_approx_unpooled"
    NEWCOMBE = "newcombe"
    STUDENT_T_DIST = "student_t_dist"
    WELCH_T_DIST = "welch_t_dist"
    HODGES_LEHMANN = "hodges_lehmann"
    PERCENTILE_BOOTSTRAP = "percentile_bootstrap"
    BCA_BOOTSTRAP = "bca_bootstrap"


class EstimateName(str, Enum):
    """Nature de l'estimé B − A.

    Toutes les méthodes ne mesurent pas la même chose : Mann-Whitney ne compare
    ni moyennes ni médianes, son estimé compagnon est celui de Hodges-Lehmann.
    """

    DIFFERENCE_OF_PROPORTIONS = "difference_of_proportions"
    DIFFERENCE_OF_MEANS = "difference_of_means"
    HODGES_LEHMANN = "hodges_lehmann"


class EffectSizeName(str, Enum):
    """Mesure d'effet standardisée, appariée à la famille de méthodes."""

    COHENS_H = "cohens_h"
    COHENS_D = "cohens_d"
    HEDGES_G = "hedges_g"
    CLIFFS_DELTA = "cliffs_delta"


class EffectSizeLabel(str, Enum):
    """Étiquette conventionnelle.

    Ce n'est **pas** un jugement de valeur : en A/B testing web, un effet
    ``NEGLIGIBLE`` au sens de Cohen peut valoir des centaines de conversions.
    L'étiquette n'est jamais affichée sans sa convention.
    """

    NEGLIGIBLE = "negligible"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class AssumptionStatus(str, Enum):
    """État d'une hypothèse de validité.

    Trois états et non un booléen : l'indépendance des observations ne peut pas
    être vérifiée depuis les données, elle dépend du protocole expérimental.
    Un booléen forcerait à mentir dans un sens ou dans l'autre.
    """

    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNVERIFIABLE = "unverifiable"


class Severity(str, Enum):
    """Gravité d'un avertissement."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class InterpretationCase(str, Enum):
    """Branche de l'arbre de décision empruntée.

    Position de l'intervalle de confiance par rapport à 0 et au seuil de
    pertinence pratique delta :

    * ``A`` — entièrement au-delà de delta : significatif **et** pertinent.
    * ``B`` — exclut 0 mais reste sous delta : significatif, trop petit pour compter.
    * ``C`` — contient 0 et tient dans ±delta : non concluant, gros effet exclu.
    * ``D`` — contient 0 et dépasse delta : non concluant, étude trop imprécise.
    * ``E`` — entièrement sous 0 : effet négatif, B dégrade la métrique.

    Les cas ``C`` et ``D`` sont tous deux « non significatifs » mais appellent
    des recommandations opposées. C'est la raison d'être de ce champ.

    Les tests portent sur cette valeur, jamais sur les phrases françaises, pour
    que celles-ci puissent être réécrites ou traduites librement.
    """

    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"


# ---------------------------------------------------------------------------
# Sous-objets
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Hypotheses:
    """Les hypothèses réellement testées par la méthode.

    Le texte est spécifique à chaque méthode et ne doit pas être générique :
    Welch teste l'égalité des moyennes, Mann-Whitney une dominance stochastique,
    la permutation l'égalité des distributions. L'export PDF doit afficher la
    formulation du test réellement exécuté.
    """

    alternative: Alternative
    null_text: str
    alternative_text: str

    def __post_init__(self) -> None:
        if not self.null_text.strip():
            raise ValueError("null_text ne peut pas être vide.")
        if not self.alternative_text.strip():
            raise ValueError("alternative_text ne peut pas être vide.")


@dataclass(frozen=True, slots=True)
class GroupSummary:
    """Résumé d'un groupe.

    Les champs binaires (``successes``, ``rate``) et continus (``mean``, ``sd``,
    ``median``) sont mutuellement exclusifs en pratique ; le champ ``n`` est le
    seul toujours présent, et il est indispensable : sans effectif, un taux est
    ininterprétable.
    """

    n: int
    successes: int | None = None
    rate: float | None = None
    mean: float | None = None
    sd: float | None = None
    median: float | None = None

    def __post_init__(self) -> None:
        if self.n < 0:
            raise ValueError(f"n doit être positif ou nul, reçu {self.n}.")
        if self.successes is not None:
            if self.successes < 0:
                raise ValueError("successes ne peut pas être négatif.")
            if self.successes > self.n:
                raise ValueError(
                    f"successes ({self.successes}) dépasse n ({self.n})."
                )
        if self.rate is not None and not 0.0 <= self.rate <= 1.0:
            raise ValueError(f"rate doit être dans [0, 1], reçu {self.rate}.")
        if self.sd is not None and self.sd < 0:
            raise ValueError("sd ne peut pas être négatif.")


@dataclass(frozen=True, slots=True)
class Groups:
    """Les deux bras de l'expérience.

    ``a`` est le contrôle (référence), ``b`` le traitement (nouveauté).
    """

    a: GroupSummary
    b: GroupSummary


@dataclass(frozen=True, slots=True)
class Statistic:
    """Statistique de test.

    Absente pour Fisher exact (qui énumère au lieu de calculer une statistique
    au sens classique) et pour le bootstrap.
    """

    name: str | None = None
    value: float | None = None
    df: float | None = None

    def __post_init__(self) -> None:
        if self.value is not None and self.name is None:
            raise ValueError(
                "Une statistique chiffrée doit porter un nom (« z », « t », « U »…)."
            )
        if self.value is not None and not math.isfinite(self.value):
            raise ValueError("La statistique doit être un nombre fini.")
        if self.df is not None and self.df <= 0:
            raise ValueError("Les degrés de liberté doivent être strictement positifs.")


@dataclass(frozen=True, slots=True)
class Estimate:
    """Estimation ponctuelle de l'effet, toujours dans le sens B − A.

    C'est le seul champ numérique jamais nul du contrat : une méthode incapable
    de produire un estimé n'a pas sa place dans le catalogue.
    """

    name: EstimateName
    value: float
    unit: str
    direction: str = EFFECT_DIRECTION

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("L'estimé doit être un nombre fini.")
        if not self.unit.strip():
            raise ValueError(
                "L'unité est obligatoire (« proportion », « euros », « seconds »…) "
                "pour éviter toute ambiguïté d'affichage."
            )
        if self.direction != EFFECT_DIRECTION:
            raise ValueError(
                f"Le sens de l'effet est fixe : {EFFECT_DIRECTION!r}. "
                "Inverser le signe casserait le module d'interprétation."
            )


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    """Fourchette de valeurs plausibles pour le vrai effet.

    Le niveau est une propriété de la **méthode**, pas de cet intervalle en
    particulier : sur un grand nombre de répétitions, 95 % des intervalles ainsi
    construits contiendraient la vraie valeur.

    Un intervalle renseigné doit obligatoirement déclarer sa construction. C'est
    ce qui permet à Fisher d'emprunter une construction (Newcombe) et à la
    permutation d'emprunter l'IC du bootstrap, sans que ce soit silencieux.
    """

    level: float
    lower: float | None = None
    upper: float | None = None
    method: CIMethod | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.level < 1.0:
            raise ValueError(
                f"Le niveau de confiance doit être dans ]0, 1[, reçu {self.level}."
            )
        bounds_set = (self.lower is not None, self.upper is not None)
        if any(bounds_set) and not all(bounds_set):
            raise ValueError(
                "Un intervalle doit avoir ses deux bornes, ou aucune des deux."
            )
        if self.lower is None:
            if self.method is not None:
                raise ValueError(
                    "Une méthode d'IC est déclarée alors qu'aucune borne n'est fournie."
                )
            return
        if self.method is None:
            raise ValueError(
                "Un intervalle de confiance doit déclarer sa construction "
                "(champ `method`)."
            )
        if not (math.isfinite(self.lower) and math.isfinite(self.upper)):
            raise ValueError("Les bornes de l'IC doivent être des nombres finis.")
        if self.lower > self.upper:
            raise ValueError(
                f"Bornes inversées : lower={self.lower} > upper={self.upper}."
            )

    @property
    def is_available(self) -> bool:
        """Vrai si l'intervalle a été calculé."""
        return self.lower is not None and self.upper is not None

    @property
    def excludes_zero(self) -> bool:
        """Vrai si l'intervalle exclut 0, donc si H0 n'est plus plausible.

        Lève une erreur si l'intervalle n'est pas disponible : mieux vaut un
        échec net qu'une réponse par défaut trompeuse.
        """
        if not self.is_available:
            raise ValueError(
                "Intervalle non disponible : impossible de dire s'il exclut 0."
            )
        return self.lower > 0.0 or self.upper < 0.0


@dataclass(frozen=True, slots=True)
class EffectSize:
    """Différence exprimée en unités de variabilité naturelle, donc sans unité.

    Répond à « de combien, rapporté à la dispersion ? », que ni la p-value ni
    l'estimé brut ne traitent.
    """

    name: EffectSizeName
    value: float
    convention: str | None = None
    label: EffectSizeLabel | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("La taille d'effet doit être un nombre fini.")
        if self.label is not None and not (self.convention or "").strip():
            raise ValueError(
                "Une étiquette de taille d'effet exige sa convention "
                "(par exemple « cohen_1988 »). Sans elle, l'étiquette devient "
                "un jugement déguisé."
            )


@dataclass(frozen=True, slots=True)
class Assumption:
    """Hypothèse de validité de la méthode.

    Une hypothèse violée n'invalide pas le code : elle invalide le **résultat**.
    D'où l'importance de les énumérer même lorsqu'elles sont satisfaites.
    """

    code: str
    description: str
    status: AssumptionStatus
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Le code d'une hypothèse est obligatoire.")
        if not self.description.strip():
            raise ValueError("La description d'une hypothèse est obligatoire.")


@dataclass(frozen=True, slots=True)
class AnalysisWarning:
    """Avertissement lisible par une machine.

    Nommé ``AnalysisWarning`` et non ``Warning`` pour ne pas masquer la classe
    intégrée de Python.

    Le champ ``code`` est stable et sert de clé : c'est lui qui permet au
    frontend d'afficher une icône, de traduire ou de filtrer. Un message en
    texte libre ne permettrait rien de tout cela.
    """

    code: str
    severity: Severity
    message: str
    affected_field: str | None = None
    suggested_alternative: Method | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Le code d'un avertissement est obligatoire.")
        if not self.message.strip():
            raise ValueError("Le message d'un avertissement est obligatoire.")


@dataclass(frozen=True, slots=True)
class Reproducibility:
    """Métadonnées permettant de rejouer l'analyse à l'identique.

    ``input_hash`` est essentiel dans une architecture sans état : puisque les
    données transitent par le navigateur et qu'aucun serveur ne les conserve,
    c'est la seule preuve de ce qui a réellement été analysé. Deux résultats
    partageant ``input_hash``, ``method`` et ``seed`` doivent être identiques.
    """

    computed_at: datetime
    input_hash: str
    library_versions: tuple[tuple[str, str], ...] = ()
    seed: int | None = None
    n_resamples: int | None = None

    def __post_init__(self) -> None:
        if self.computed_at.tzinfo is None:
            raise ValueError(
                "computed_at doit porter un fuseau horaire (UTC de préférence) : "
                "une date sans fuseau n'est pas reproductible."
            )
        if not self.input_hash.strip():
            raise ValueError("input_hash est obligatoire.")
        if isinstance(self.library_versions, Mapping):
            object.__setattr__(
                self,
                "library_versions",
                tuple(sorted(self.library_versions.items())),
            )
        if self.n_resamples is not None and self.n_resamples <= 0:
            raise ValueError("n_resamples doit être strictement positif.")

    @property
    def versions(self) -> dict[str, str]:
        """Les versions de bibliothèques sous forme de dictionnaire."""
        return dict(self.library_versions)


# ---------------------------------------------------------------------------
# Le contrat
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StatisticalResult:
    """Résultat d'une analyse, identique en forme pour les sept méthodes.

    L'objet est **auto-suffisant** : il porte les effectifs et les hypothèses
    testées, de sorte qu'un export PDF soit lisible sans accéder à
    l'application.

    Il ne contient délibérément **pas** l'interprétation : celle-ci dépend du
    seuil de pertinence pratique delta, une donnée métier qui ne doit avoir
    aucune influence sur les calculs. Voir :class:`Interpretation`.
    """

    method: Method
    metric_type: MetricType
    hypotheses: Hypotheses
    groups: Groups
    statistic: Statistic
    alpha: float
    decision: Decision
    estimate: Estimate
    confidence_interval: ConfidenceInterval
    effect_size: EffectSize
    reproducibility: Reproducibility
    p_value: float | None = None
    p_value_source: PValueSource | None = None
    relative_lift: float | None = None
    n_excluded: int = 0
    assumptions: tuple[Assumption, ...] = ()
    warnings: tuple[AnalysisWarning, ...] = ()
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise ValueError(f"alpha doit être dans ]0, 1[, reçu {self.alpha}.")
        if self.n_excluded < 0:
            raise ValueError("n_excluded ne peut pas être négatif.")

        if self.p_value is not None:
            if not 0.0 <= self.p_value <= 1.0:
                raise ValueError(
                    f"Une p-value doit être dans [0, 1], reçu {self.p_value}."
                )
            if self.p_value_source is None:
                raise ValueError(
                    "Une p-value doit déclarer sa provenance (`p_value_source`)."
                )
            # Cohérence du verdict. Convention : on rejette si p <= alpha.
            if self.decision is not Decision.NOT_APPLICABLE:
                expected = (
                    Decision.REJECT_NULL
                    if self.p_value <= self.alpha
                    else Decision.FAIL_TO_REJECT_NULL
                )
                if self.decision is not expected:
                    raise ValueError(
                        f"Verdict incohérent : p={self.p_value} avec "
                        f"alpha={self.alpha} impose {expected.value!r}, "
                        f"mais {self.decision.value!r} a été fourni."
                    )
        elif self.p_value_source is not None:
            raise ValueError(
                "`p_value_source` est renseigné sans p-value correspondante."
            )

        if self.relative_lift is not None and not math.isfinite(self.relative_lift):
            raise ValueError("Le lift relatif doit être un nombre fini.")

        if not isinstance(self.assumptions, tuple):
            raise TypeError("`assumptions` doit être un tuple, pas une liste.")
        if not isinstance(self.warnings, tuple):
            raise TypeError("`warnings` doit être un tuple, pas une liste.")

    @property
    def is_significant(self) -> bool:
        """Vrai si H0 a été rejetée.

        Ne signifie pas que l'effet est important : voir :attr:`effect_size` et
        le seuil de pertinence pratique.
        """
        return self.decision is Decision.REJECT_NULL

    @property
    def has_critical_warning(self) -> bool:
        """Vrai si au moins un avertissement remet en cause la validité."""
        return any(w.severity is Severity.CRITICAL for w in self.warnings)

    @property
    def violated_assumptions(self) -> tuple[Assumption, ...]:
        """Les hypothèses de validité vérifiées et non respectées."""
        return tuple(
            a for a in self.assumptions if a.status is AssumptionStatus.VIOLATED
        )


# ---------------------------------------------------------------------------
# Interprétation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Interpretation:
    """Lecture déterministe d'un résultat, à la lumière du seuil ``delta``.

    Objet séparé de :class:`StatisticalResult` parce qu'il dépend d'une donnée
    métier : le seuil de pertinence pratique fixé par l'analyste. Cette
    séparation permet de faire varier ``delta`` et de régénérer l'interprétation
    sans recalculer la statistique.

    Aucune phrase produite ici ne doit affirmer que les groupes sont égaux : une
    preuve insuffisante n'est pas une preuve d'absence.
    """

    case: InterpretationCase
    significance_statement: str
    practical_statement: str
    recommendation: str
    delta: float | None = None
    caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("significance_statement", "practical_statement", "recommendation"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} ne peut pas être vide.")
        if self.delta is not None:
            if not math.isfinite(self.delta):
                raise ValueError("delta doit être un nombre fini.")
            if self.delta < 0:
                raise ValueError(
                    "delta est une amplitude minimale : il doit être positif ou nul."
                )
        # Les cas A à D situent l'intervalle par rapport à delta ; ils sont
        # indéfinis sans lui. Seul le cas E (effet négatif significatif) se
        # passe de delta.
        elif self.case is not InterpretationCase.E:
            raise ValueError(
                f"Le cas {self.case.value!r} se définit par rapport au seuil de "
                "pertinence pratique : `delta` est obligatoire."
            )
        if not isinstance(self.caveats, tuple):
            raise TypeError("`caveats` doit être un tuple, pas une liste.")


@dataclass(frozen=True, slots=True)
class AnalysisOutcome:
    """Ce que l'API renvoie : le fait scientifique, puis sa lecture."""

    result: StatisticalResult
    interpretation: Interpretation | None = None
