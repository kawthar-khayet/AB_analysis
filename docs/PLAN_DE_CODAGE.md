# Plan de codage — A/B Analysis Workspace

Document de travail. Chaque étape est une unité de code autonome, terminée par un critère vérifiable.

**Règle de travail :** aucun fichier n'est rempli sans accord explicite. On avance étape par étape, une étape = un accord.

**Documents de référence :**
- `../Rapport_Conception_AB_Analysis_Workspace.md` — architecture et fondements statistiques
- `CONTRAT_StatisticalResult.md` — le contrat détaillé (à rédiger à l'étape 1)
- `CATALOGUE_METHODES.md` — les 7 méthodes et leurs hypothèses (à rédiger à l'étape 12)

---

## Rôle de chaque fichier

### `packages/ab_stats/` — le paquet scientifique

> **Interdiction absolue :** aucun `import fastapi`, aucune notion de HTTP, JSON ou requête dans ce dossier.

| Fichier | Rôle |
|---|---|
| `results.py` | Le contrat `StatisticalResult` et ses sous-objets. Aucune logique de calcul. |
| `data.py` | Profilage des colonnes, déclarations de l'analyste, validation et normalisation ; produit le rapport d'exclusions. |
| `exceptions.py` | Erreurs structurées : code stable, catégorie, message, détails sérialisables. |
| `simulation.py` | Génération déterministe de données A/B (binaires et continues) à partir d'une graine. |
| `diagnostics.py` | Effectifs, valeurs manquantes, statistiques descriptives, asymétrie, valeurs extrêmes. |
| `effect_sizes.py` | `cohens_d`, `hedges_g`, `cohens_h`, `cliffs_delta`. |
| `confidence_intervals.py` | Constructions d'IC réutilisables (normal, percentile bootstrap, Hodges–Lehmann). |
| `compatibility.py` | Moteur de compatibilité : quelles méthodes sont applicables, avec quels avertissements. |
| `interpretation.py` | Arbre de décision déterministe (cas a → e) produisant l'objet `Interpretation`. |
| `methods/proportions.py` | `two_proportion_z`, `fisher_exact`. |
| `methods/ttests.py` | `student_t`, `welch_t`. |
| `methods/mann_whitney.py` | `mann_whitney_u` + estimateur de Hodges–Lehmann. |
| `methods/permutation.py` | Test de permutation sur la différence des moyennes. |
| `methods/bootstrap.py` | Bootstrap de la différence. |

### `backend/app/` — la frontière typée

| Fichier | Rôle |
|---|---|
| `main.py` | Application FastAPI, montage des routes, CORS. |
| `schemas.py` | Schémas Pydantic requête/réponse. Traduisent `ab_stats` en JSON, sans calculer. |
| `routes/health.py` | `GET /api/v1/health` |
| `routes/datasets.py` | `POST /datasets/import`, `POST /simulations`, `POST /diagnostics` |
| `routes/analyses.py` | `POST /analyses`, `GET /methods` |
| `routes/exports.py` | `POST /exports/pdf` |
| `services/analysis_service.py` | Orchestration : valider → appeler `ab_stats` → assembler la réponse. |
| `services/export_service.py` | Génération du rapport PDF. |

### `frontend/src/` — le workspace

| Fichier | Rôle |
|---|---|
| `layout/WorkspaceLayout.tsx` | La coquille : sidebar + zone de travail. |
| `layout/StepNav.tsx` | Les 5 entrées et leurs indicateurs ✓ / ● / ○. |
| `state/workspaceState.ts` | L'état de session (dataset, mapping, diagnostics, méthode, résultat) + persistance. |
| `api/client.ts` | Client HTTP de base, gestion des erreurs structurées. |
| `api/endpoints.ts` | Une fonction typée par endpoint. |
| `types/results.ts` | Miroir TypeScript de `StatisticalResult`. |
| `types/dataset.ts` | Types du dataset, du mapping et du rapport de validation. |
| `pages/*.tsx` | Les 5 étapes du workflow. |
| `components/MissingPrerequisite.tsx` | Le bloc « il manque X, va à l'étape Y ». |
| `components/ResultCard.tsx` | Affichage d'un `StatisticalResult`. |
| `components/ConfidenceIntervalPlot.tsx` | La barre d'IC avec 0 et δ marqués. |
| `components/WarningList.tsx` | Rendu des warnings machine-readable. |

---

# Phase 0 — Préparation

## Étape 0.1 — Environnement Python

**Fichiers :** `packages/pyproject.toml`, `backend/pyproject.toml`, `.gitignore`

**Contenu :** métadonnées du paquet `ab_stats` (dépendances : `numpy`, `scipy`, `statsmodels`) et du backend (`fastapi`, `uvicorn`, `pydantic`, `ab_stats` en editable). Aucun code.

**Fait quand :** `pip install -e ./packages` réussit et `python -c "import ab_stats"` ne lève rien.

---

# Phase 1 — Le noyau statistique

> Objectif de la phase : obtenir un résultat statistique complet et vérifié, **sans serveur ni interface**.

## Étape 1 — `results.py` : le contrat ✅

**Fichier :** `packages/ab_stats/results.py`
**Test :** `tests/test_results.py`

Les dataclasses `frozen=True` : `StatisticalResult`, `Hypotheses`, `GroupSummary`, `Statistic`, `Estimate`, `ConfidenceInterval`, `EffectSize`, `Assumption`, `Warning`, `Reproducibility`, `Interpretation`. Plus les énumérations `Method`, `MetricType`, `Decision`, `Alternative`, `AssumptionStatus`, `Severity`.

**⚠️ Prérequis — trois décisions à trancher avant d'écrire ce fichier :**
1. IC de Fisher exact : `null` + warning, ou calcul par une autre approche déclarée ?
2. IC de la permutation et p-value du bootstrap : `null`, ou complément explicite déclaré dans `method` / `p_value_source` ?
3. `effect_size.label` : le stocker avec sa `convention` obligatoire, ou le laisser au frontend ?

**Fait quand :** on peut construire un `StatisticalResult` à la main en Python, il est immuable, et `tests/test_results.py` vérifie qu'une tentative de modification échoue.

**Pourquoi en premier :** tout le reste retourne cet objet. Le définir après les méthodes obligerait à tout réécrire.

## Étape 2 — `data.py` : validation et normalisation ✅

**Fichier :** `packages/ab_stats/data.py` · **Test :** `tests/test_data.py`

Prend deux colonnes brutes (`group`, `metric`), applique le mapping (valeur A, valeur B), détecte le type de métrique, exclut les lignes invalides **en enregistrant le motif**, et renvoie un objet normalisé + un rapport d'exclusions.

**Fait quand :** les tests couvrent — valeurs manquantes, valeurs non numériques, groupe inconnu, groupe vide, métrique binaire non 0/1 (`"yes"`/`"no"`), colonnes de longueurs différentes.

**Règle :** ne jamais corriger silencieusement. Toute ligne écartée apparaît dans le rapport.

## Étape 3 — `simulation.py` : données déterministes ✅

**Fichier :** `packages/ab_stats/simulation.py` · **Test :** `tests/test_simulation.py`

Génère une expérience binaire (taux A, taux B, n par groupe) ou continue (moyenne, écart-type), à partir d'une **graine explicite**.

**Fait quand :** deux appels avec la même graine produisent des tableaux strictement identiques ; deux graines différentes produisent des tableaux différents.

## Étape 4 — `diagnostics.py`

**Fichier :** `packages/ab_stats/diagnostics.py` · **Test :** `tests/test_diagnostics.py`

Effectifs par groupe, valeurs manquantes, taux (binaire) ou moyenne/écart-type/médiane/quartiles (continu), asymétrie, détection de valeurs extrêmes, rapport des variances.

**Fait quand :** les sorties sont comparées à des valeurs calculées à la main sur un petit jeu de données de 10 lignes.

**Pourquoi avant les méthodes :** c'est `compatibility.py` (étape 8) qui consommera ces diagnostics pour émettre ses warnings.

## Étape 5 — `effect_sizes.py` et `confidence_intervals.py`

**Fichiers :** les deux · **Tests :** `test_effect_sizes.py`, `test_confidence_intervals.py`

Fonctions pures, sans dépendance aux méthodes. Vérifier notamment que `cohens_h(0.01, 0.02) ≈ 0.084` et `cohens_h(0.50, 0.51) ≈ 0.020` — l'exemple du rapport §13.

**Fait quand :** chaque fonction est testée sur au moins un cas dont la valeur attendue est connue indépendamment.

## Étape 6 — `methods/proportions.py` : le z-test

**Fichier :** `packages/ab_stats/methods/proportions.py` · **Test :** `tests/test_proportions.py`

La fonction `two_proportion_z(...)` retourne un `StatisticalResult` complet : hypothèses, statistique, p-value, estimé, IC, taille d'effet, `assumptions`, `warnings`, `reproducibility`.

**Fait quand :** sur le scénario du rapport (5 550/50 000 contre 6 200/50 000) on retrouve `z ≈ 6,383`, `p ≈ 1,7e-10`, `IC ≈ [0,0090 ; 0,0170]`, `h ≈ 0,0403`.

**C'est l'étape charnière du projet.** Le premier résultat complet.

## Étape 7 — `methods/ttests.py` : Welch puis Student

**Fichier :** `packages/ab_stats/methods/ttests.py` · **Test :** `tests/test_ttests.py`

Welch d'abord (le défaut recommandé), Student ensuite (trivial une fois Welch écrit). **Aucun pré-test de variance ne doit choisir automatiquement entre les deux.**

**Fait quand :** les résultats coïncident avec `scipy.stats.ttest_ind(..., equal_var=False)` et `equal_var=True`.

## Étape 8 — `compatibility.py` : le moteur

**Fichier :** `packages/ab_stats/compatibility.py` · **Test :** `tests/test_compatibility.py`

À partir de `metric_type` + diagnostics, renvoie pour chaque méthode : `compatible`, `assumptions`, `warnings`. Les codes de warning : `LOW_EVENT_COUNT`, `SMALL_SAMPLE`, `HIGH_SKEWNESS`, `OUTLIERS_DETECTED`, `UNEQUAL_VARIANCES`, `ZERO_VARIANCE`, `UNBALANCED_GROUPS`, `MISSING_VALUES_EXCLUDED`.

**Fait quand :** un t-test sur métrique binaire est déclaré **incompatible** (absent, pas grisé) ; un z-test avec 4 succès déclenche `LOW_EVENT_COUNT` avec `suggested_alternative = "fisher_exact"`.

## Étape 9 — `interpretation.py` : l'arbre de décision

**Fichier :** `packages/ab_stats/interpretation.py` · **Test :** `tests/test_interpretation.py`

Implémente les cinq cas (a → e) du rapport §15. Prend un `StatisticalResult` **et** un δ optionnel, retourne un `Interpretation` avec son champ `case`.

**Fait quand :** les tests portent sur le champ `case`, jamais sur les chaînes de caractères françaises — les phrases doivent pouvoir être réécrites sans casser un test. Cas obligatoires : IC `[−0,3 ; +0,5]` avec δ = 1,0 → `case = "c"` ; IC `[−1,5 ; +4,1]` avec δ = 1,0 → `case = "d"`.

**Vérification interdite :** aucune phrase produite ne doit contenir « A et B sont égaux » ou équivalent.

## Étape 10 — Tests de référence

**Fichier :** `tests/test_reference_scipy.py`

Comparaison systématique de chaque méthode implémentée à SciPy/Statsmodels, plus une vérification Monte-Carlo : sous H₀ vraie, le taux de rejet doit avoisiner α (test A/A simulé, quelques milliers de répétitions).

**Fait quand :** `pytest` passe intégralement. **Fin de la phase 1 : le noyau scientifique est fiable.**

---

# Phase 2 — La couche API

## Étape 11 — `schemas.py` et `main.py` + `health`

**Fichiers :** `backend/app/schemas.py`, `main.py`, `routes/health.py` · **Test :** `tests/test_health.py`

Les schémas Pydantic miroir du contrat, l'application FastAPI, le CORS, et le health check.

**Fait quand :** `GET /api/v1/health` répond `200` et `/docs` affiche les schémas.

## Étape 12 — `routes/datasets.py`

**Fichiers :** `routes/datasets.py` · **Test :** `tests/test_datasets.py`

`POST /datasets/import` (valide et **renvoie** les données, ne stocke rien), `POST /simulations`, `POST /diagnostics`.

**Fait quand :** un CSV avec des lignes invalides revient avec ses données nettoyées **et** son rapport d'exclusions. Un payload dépassant la limite de taille est refusé avec un message clair.

## Étape 13 — `routes/analyses.py` et le service

**Fichiers :** `routes/analyses.py`, `services/analysis_service.py` · **Test :** `tests/test_analyses.py`

`GET /methods` (alimenté par `compatibility.py`) et `POST /analyses`.

**Règle de sécurité de la Décision A :** le service **revalide** les données à chaque appel. Ne jamais supposer qu'un payload est propre parce qu'il est passé par `/import`.

**Fait quand :** un appel bout en bout renvoie le même `StatisticalResult` que l'appel direct au paquet Python, et un payload corrompu est rejeté proprement.

---

# Phase 3 — Le workspace React

## Étape 14 — Échafaudage et types

**Fichiers :** `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `main.tsx`, `types/*.ts`, `api/*.ts`

Les types TypeScript sont le **miroir exact** du contrat. Aucune formule statistique dans ce dossier.

**Fait quand :** `npm run dev` démarre et un appel à `/health` s'affiche dans la console.

## Étape 15 — Layout et état de session

**Fichiers :** `layout/WorkspaceLayout.tsx`, `layout/StepNav.tsx`, `state/workspaceState.ts`, `components/MissingPrerequisite.tsx`

La sidebar, la zone de travail, les indicateurs ✓ / ● / ○, la **navigation libre**, et la persistance `sessionStorage`.

**Fait quand :** on peut cliquer sur les 5 entrées à tout moment ; une page sans prérequis affiche le bloc explicatif ; un F5 ne perd pas l'état.

## Étape 16 — Pages Dataset et Diagnostics

**Fichiers :** `pages/Dataset.tsx`, `pages/Diagnostics.tsx`

Import CSV ou simulation, aperçu, mapping des colonnes, affichage du rapport d'exclusions ; puis effectifs, statistiques descriptives et graphiques.

**Fait quand :** un CSV importé est mappé et ses diagnostics s'affichent.

## Étape 17 — Pages Method et Results

**Fichiers :** `pages/Method.tsx`, `pages/Results.tsx`, `components/ResultCard.tsx`, `ConfidenceIntervalPlot.tsx`, `WarningList.tsx`

La liste des méthodes compatibles avec leurs hypothèses et warnings, le choix explicite, puis l'affichage du résultat.

**Règles d'affichage :**
- jamais de p-value seule ;
- `p < 0,001` plutôt que `p = 0.000` ;
- l'étiquette de taille d'effet toujours suffixée de sa convention ;
- le curseur δ modifie l'interprétation **sans** relancer l'analyse.

**Fait quand :** le workflow complet Dataset → Diagnostics → Method → Results fonctionne avec le z-test et Welch. **Fin de la phase 3 : le projet est démontrable.**

---

# Phase 4 — Complétion

## Étape 18 — Les cinq méthodes restantes

Dans cet ordre, une étape par méthode : `fisher_exact` → `mann_whitney_u` → `permutation` → `bootstrap` → `student_t`.

**Pourquoi cet ordre :** chacune met le contrat à l'épreuve sur un point différent — Fisher sur l'IC, Mann-Whitney sur l'estimé non standard, permutation et bootstrap sur la graine et les champs `null`.

**Fait quand :** aucune modification du contrat n'a été nécessaire pour les accueillir. Si le contrat doit changer, c'est un signal — on en discute avant.

## Étape 19 — Export

**Fichiers :** `services/export_service.py`, `routes/exports.py`, `pages/Export.tsx`

JSON, CSV, et rapport PDF contenant : les hypothèses réellement testées, les effectifs, le résultat complet, les warnings, l'interprétation et les métadonnées de reproductibilité.

**Fait quand :** le PDF est lisible seul, sans accès à l'application.

## Étape 20 — Reproductibilité et conteneurisation

**Fichiers :** `docker-compose.yml`, `README.md`, `examples/*.csv`

**Fait quand :** deux exécutions avec le même `input_hash`, la même méthode et la même graine produisent des résultats identiques ; `docker compose up` lance le workflow complet.

---

## Récapitulatif

| Phase | Étapes | Résultat |
|---|---|---|
| 0 — Préparation | 0.1 | Environnement installable |
| 1 — Noyau statistique | 1 → 10 | Résultats corrects et vérifiés contre SciPy, sans serveur |
| 2 — API | 11 → 13 | Endpoints typés et testés indépendamment |
| 3 — Workspace | 14 → 17 | Workflow complet démontrable avec 2 méthodes |
| 4 — Complétion | 18 → 20 | 7 méthodes, exports, Docker |

**Prochaine action :** trancher les trois décisions de l'étape 1, puis écrire `results.py`.
