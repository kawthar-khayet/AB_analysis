# Guide d'import CSV

Ce document décrit ce que l'application accepte en entrée, comment déclarer les groupes A et B, ce qui est écarté et pourquoi, et comment corriger les erreurs les plus fréquentes.

**Principe directeur :** l'application ne corrige jamais vos données en silence. Elle écarte ce qui est inutilisable en le comptant, elle normalise ce qui est un simple format en le déclarant, et elle s'arrête pour vous demander dès qu'un choix vous appartient.

---

## Table des matières

1. [Format accepté](#1-format-accepté)
2. [Mapping A/B](#2-mapping-ab)
3. [Exclusions et sortie normalisée](#3-exclusions-et-sortie-normalisée)
4. [Erreurs fréquentes](#4-erreurs-fréquentes)

---

# 1. Format accepté

## Un seul fichier

L'application prend **un fichier CSV**, contenant à la fois l'assignation aux groupes et la métrique mesurée. Il n'y a pas de jointure entre plusieurs fichiers : si vos données sont réparties dans plusieurs exports, joignez-les avant l'import.

## Structure attendue

```
visitor_id,variant,converted
B001,control,0
B002,treatment,1
B003,control,1
B004,treatment,0
B005,control,0
B006,treatment,1
B007,control,1
B008,treatment,1
```

| Règle | Détail |
|---|---|
| **Une ligne = un participant** | Chaque ligne décrit une personne et une seule |
| **Ligne d'en-tête obligatoire** | La première ligne donne les noms de colonnes |
| **Deux colonnes utiles** | Une colonne de groupe, une colonne de métrique |
| **Colonnes supplémentaires** | Ignorées, elles peuvent rester dans le fichier |
| **Exactement deux groupes analysés** | L'application compare toujours A contre B, jamais davantage |

Dans l'exemple ci-dessus, `visitor_id` n'est pas utilisé par l'analyse — il peut rester, il est simplement ignoré.

## Délimiteurs

Le délimiteur est **détecté automatiquement** parmi :

```
,   virgule            visitor_id,variant,converted
;   point-virgule      visitor_id;variant;converted
\t  tabulation         visitor_id	variant	converted
```

Le point-virgule est le format par défaut d'Excel en configuration française — il est pleinement supporté.

## Encodage

**UTF-8 recommandé.** Un fichier réencodé depuis Excel peut contenir des accents mal lus (`contrôle` devenant `contrÃ´le`). Si vous voyez des caractères étranges dans l'aperçu, réexportez en UTF-8.

## Métriques acceptées

L'application ne traite que **deux types** de métrique.

### Binaire — « l'événement a-t-il eu lieu ? »

Valeurs `0` et `1` :

```
converted
0
1
0
1
```

Ou **deux valeurs quelconques**, à condition de déclarer laquelle représente le succès :

```
converted          purchased          status
yes                true               A
no                 false              B
yes                true               A
```

L'application détecte qu'il n'y a que deux valeurs distinctes et vous demande de déclarer l'encodage :

```
Metric has 2 distinct values: "yes" · "no"

Which one is the success (1) ?
   ○ yes        ○ no
```

Le codage déclaré est enregistré dans le rapport de validation.

### Continue — « de combien ? »

Un nombre par participant : montant, durée, nombre de pages.

```
cart_value
49.90
0.00
132.75
27.30
```

### Ce qui n'est pas accepté

Une colonne textuelle à **plus de deux valeurs distinctes** (`"faible"`, `"moyen"`, `"élevé"`). L'application ne traite pas les métriques ordinales — voyez [Erreurs fréquentes](#unsupported_metric).

## Séparateur décimal

Le point et la virgule sont acceptés :

```
cart_value        cart_value
49.90             49,90
32.50             32,50
```

**La décision se prend par colonne, pas par valeur.** Si toutes les valeurs de la colonne utilisent la virgule et aucune n'utilise le point, l'application convertit l'ensemble et l'enregistre :

```
decimal_separator : ","  →  converted to "."  (1 284 values)
```

Deux cas où l'application refuse de deviner :

| Situation | Raison |
|---|---|
| Points **et** virgules mélangés (`1,234.56`) | Convention ambiguë |
| Toutes les valeurs ont exactement 3 chiffres après la virgule (`1,234` · `5,678`) | Ressemble à un séparateur de milliers |

Dans ces cas, l'application affiche un avertissement et vous demande.

> ⚠️ **Attention au fichier séparé par des virgules contenant des décimales à la virgule.** `B001,control,49,90` produit **quatre** champs pour un en-tête à trois colonnes. C'est bloquant — voyez [Erreurs fréquentes](#field-count-mismatch).

## Taille maximale

**5 Mio par défaut**, vérifiée par le backend au moment du téléversement, avant toute lecture du fichier (même choix qu'ExperimentOS).

Au-delà, l'import est refusé avec un message explicite plutôt que de laisser le navigateur ramer.

---

# 2. Mapping A/B

## Ce que vous devez déclarer

Un fichier CSV ne dit nulle part quelle colonne contient les groupes, ni laquelle de ses valeurs est le contrôle. **Trois déclarations vous incombent** :

```
1. Quelle colonne contient le groupe ?        →  variant
2. Quelle valeur est A, laquelle est B ?      →  A = "control", B = "treatment"
3. Quelle colonne est la métrique ?           →  converted
```

L'application ne devine aucune des trois. Les noms de colonnes varient trop d'un outil à l'autre (`variant`, `bucket`, `ab_test_flag`, `cohorte`), et rien ne garantit que la valeur nommée `A` soit le contrôle.

## Pourquoi le sens compte

L'effet mesuré est **toujours** calculé dans le sens **B − A**.

```
A = "control",   B = "treatment"   →  estimé = +1,3 pp  →  « B est meilleur »   →  déployer
A = "treatment", B = "control"     →  estimé = −1,3 pp  →  « B est pire »       →  ne pas déployer
```

Les mêmes données, la recommandation opposée. **Vérifiez ce mapping avant de lancer l'analyse.**

Convention :

| | |
|---|---|
| **A** | Le contrôle — la version de référence, l'existant |
| **B** | Le traitement — la nouveauté que vous testez |

## Quand la colonne contient plus de deux valeurs

L'application ne refuse pas le fichier. Elle affiche ce qu'elle a trouvé, avec les décomptes :

```
⚠ Group column contains 3 distinct values (2 expected)

   control        2 410 rows   (49,9 %)
   treatment      2 398 rows   (49,7 %)
   Control            6 rows   ( 0,1 %)   ← ressemble à "control" (casse)

   Map exactly 2 values as A and B.
   Remaining rows will be excluded and recorded.

   A = [ control   ▾ ]     B = [ treatment ▾ ]
   → 6 rows will be excluded (UNMAPPED_GROUP_VALUE)
```

Deux situations très différentes produisent cet écran :

**Cas 1 — données sales.** `Control` et `control` sont le même groupe, écrits différemment. L'application **signale la ressemblance** mais ne fusionne rien : corrigez votre fichier, ou acceptez l'exclusion des 6 lignes.

Différences courantes, dont certaines invisibles à l'œil :

```
"control"  vs  "Control"        casse
"control"  vs  "control "       espace final
"control"  vs  " control"       espace initial
"control"  vs  "contrôle"       deux exports, deux langues
```

**Cas 2 — expérience à plusieurs bras.** Votre fichier contient `control`, `variant_blue`, `variant_green`. L'application ne compare que deux groupes : choisissez la paire, les autres lignes seront exclues et comptées.

## Détection du type de métrique

Une fois la métrique choisie, l'application propose un type **et montre ses preuves** :

```
Detected: BINARY

Why:
   2 distinct values found — {0, 1}
   4 820 rows analysed, 0 missing

   0  →  4 285 rows  (88,9 %)
   1  →    535 rows  (11,1 %)

[ Confirm binary ]   [ Treat as continuous ]
```

**La proposition n'est jamais appliquée sans votre confirmation.** Regardez la répartition avant de valider : si elle vous surprend, le problème est peut-être dans vos données.

---

# 3. Exclusions et sortie normalisée

## Ce qui est écarté, et pourquoi

Une ligne est écartée quand elle ne peut pas participer au calcul. Quatre motifs, tous comptés et rapportés :

| Code | Situation |
|---|---|
| `MISSING_GROUP` | La case de la colonne groupe est vide |
| `MISSING_METRIC` | La case de la colonne métrique est vide |
| `NON_NUMERIC_METRIC` | Métrique continue non convertible en nombre fini (`"n/a"`, `"?"`, booléen, infini) |
| `UNMAPPED_GROUP_VALUE` | Le groupe n'est ni A ni B, exclusion confirmée par vous |

**Aucune valeur n'est jamais inventée.** Une case vide n'est pas remplacée par zéro : la ligne sort de l'analyse.

Seules les cellules **vides** comptent comme manquantes. `"n/a"` est une valeur, non numérique.

Une ligne n'est exclue que pour **un seul motif**, le premier rencontré dans l'ordre du tableau. Les indices de lignes donnés en exemple commencent à 0 à la première ligne de données.

## L'ordre des opérations

L'ordre importe, il évite des messages trompeurs :

```
1. Contrôles structurels        colonnes cohérentes, jeu non vide
2. Contrôles de mapping         A et B existent ; autres valeurs → confirmation
3. Exclusions ligne par ligne   les 4 motifs ci-dessus
4. Validation du type déclaré   sur les lignes NON EXCLUES seulement
5. Contrôles post-exclusion     A non vide, B non vide, il reste des lignes
6. Avertissements informatifs
7. Construction de la sortie
```

L'étape 4 arrive **après** l'étape 3, et **avant** l'étape 5 : si une métrique binaire contient `yes`/`no` sans codage déclaré, le vrai problème est le codage, pas un groupe vide. Autrement dit, une valeur aberrante située dans une ligne déjà exclue ne déclenche aucune alerte — elle ne fait pas partie de votre analyse.

Exemple : si `variant_green` est exclu et qu'une de ses lignes contient `converted = 2`, l'application ne signale rien. Ce serait un faux positif déroutant.

## Ce que vous récupérez

```
Jeu de données normalisé
   groupe A          les valeurs métriques de A
   groupe B          les valeurs métriques de B
   type de métrique  celui que VOUS avez déclaré
   unité             "proportion", "euros", "secondes"…

Rapport de validation
   n_input           lignes reçues
   n_retained        lignes analysées
   n_excluded        total écarté
   exclusions        par motif : code, décompte, exemples de lignes
   normalisations    séparateur décimal, encodage binaire déclaré
   avertissements    structures lisibles par la machine
```

## Un rapport de validation type

```
n_input     = 4 820
n_retained  = 4 487
n_excluded  =   333   (6,9 %)

EXCLUSIONS
   UNMAPPED_GROUP_VALUE   312   "variant_green", exclusion confirmée
   MISSING_METRIC          12   lignes 47, 288, 1902, …
   MISSING_GROUP            6   lignes 120, 3301, …
   NON_NUMERIC_METRIC       3   "n/a" — lignes 91, 1204, 3877

NORMALISATIONS DÉCLARÉES
   decimal_separator      ","  →  "."      (4 487 valeurs)

AVERTISSEMENTS
   SIMILAR_GROUP_VALUES   "Control" ressemble à "control"
```

**Ce rapport voyage jusqu'au PDF exporté.** C'est ce qui garantit que personne ne pourra prétendre plus tard que l'analyse portait sur les 4 820 lignes du fichier.

---

# 4. Erreurs fréquentes

## Tableau de synthèse

**Erreurs bloquantes**

| Code | Cause | Correction |
|---|---|---|
| `BINARY_VALIDATION_FAILED` | Type binaire déclaré, valeurs hors `{0,1}` | Choisir un traitement, déclarer un codage, ou passer en continu |
| `BINARY_ENCODING_INCOMPLETE` | Codage déclaré (`yes`/`no`), mais d'autres valeurs présentes (`YES`, `maybe`) | Corriger le fichier — la correspondance est exacte |
| `UNMAPPED_GROUP_VALUES` | La colonne groupe contient d'autres valeurs que A et B | Confirmer leur exclusion, ou corriger le mapping |
| `GROUP_VALUE_NOT_FOUND` | La valeur déclarée n'existe pas dans la colonne | Vérifier la casse et les espaces (suggestions fournies) |
| `GROUP_MAPPING_INCOMPLETE` | A et B identiques, ou vides | Choisir deux valeurs distinctes |
| `DECIMAL_SEPARATOR_MISMATCH` | Nombres écrits avec l'autre séparateur que celui déclaré | Déclarer le bon séparateur |
| `FIELD_COUNT_MISMATCH` | Décimales à la virgule dans un fichier séparé par des virgules *(détecté à la lecture du fichier)* | Réexporter en point-virgule, ou protéger par des guillemets |
| `EMPTY_DATASET` | Aucune ligne de données | Vérifier le fichier |
| `EMPTY_GROUP` | Après exclusions, un groupe est vide | Vérifier le mapping et le taux d'exclusion |
| `ALL_ROWS_EXCLUDED` | Plus aucune ligne exploitable | Vérifier le mapping — souvent une erreur de colonne |

**Avertissements** — l'analyse continue

| Code | Cause | Conseil |
|---|---|---|
| `SIMILAR_GROUP_VALUES` | Une valeur exclue ressemble à A ou B (`Control` / `control`) | Corriger le fichier si c'est le même groupe |
| `CONTINUOUS_WITH_TWO_VALUES` | Continu déclaré sur 2 valeurs | Les méthodes binaires sont sans doute plus adaptées |
| `HIGH_EXCLUSION_RATE` | Plus de 10 % des lignes écartées | Vérifier la qualité de l'export |
| `ZERO_VARIANCE` | Un groupe est constant | Aucun test ne pourra mesurer de variation dans ce groupe |

Un type de métrique proposé `unsupported` (texte à plus de deux valeurs) apparaît dès le profilage de la colonne, avant toute déclaration.

**Erreur interne** : `COLUMN_LENGTH_MISMATCH` signale un bug de l'application, pas un problème de votre fichier.

---

## `BINARY_VALIDATION_FAILED`

Le cas le plus fréquent. Vous avez déclaré la métrique binaire, mais elle contient autre chose que `0` et `1` :

```
visitor_id,variant,purchased
B001,control,0
B002,treatment,1
B003,control,2        ← cet utilisateur a acheté deux fois
```

```
⚠ Binary metric validation failed

You declared:  purchased = binary
Expected:      {0, 1}
Found also:    2        (25 rows, 0,5 %)

Please review your metric or mapping.
```

**Pourquoi l'application ne corrige pas toute seule.** Il existe trois façons raisonnables de traiter ce `2`, et elles donnent **trois résultats différents** :

| Traitement | Question réellement posée | Estimé B − A |
|---|---|---|
| Exclure les lignes contenant `2` | « parmi ceux qui ont acheté au plus une fois… » | +2,61 pp |
| Coder `2 → 1` | « quelle proportion a acheté au moins une fois ? » | +3,00 pp |
| Passer en continu | « combien d'achats par visiteur ? » | +0,035 achat |

Seule la personne qui connaît l'expérience sait laquelle est la bonne. L'application vous propose donc les trois, et enregistre votre choix.

---

<a id="field-count-mismatch"></a>
## `FIELD_COUNT_MISMATCH`

```
visitor_id,variant,cart_value
B001,control,49,90        ← 4 champs pour un en-tête à 3 colonnes
```

```
✗ Line 2: 4 fields found, 3 expected
  (header: visitor_id, variant, cart_value)
```

**Pourquoi c'est bloquant.** Ces octets sont indiscernables d'un fichier légitime à quatre colonnes :

```
visitor_id,variant,cart_value,items
B001,control,49,90            → cart_value = 49  ·  items = 90
```

L'application ne peut pas savoir si `49,90` est un nombre décimal ou deux champs.

**Corrections possibles :**

```
✅ réexporter avec des points-virgules
   visitor_id;variant;cart_value
   B001;control;49,90

✅ protéger le champ par des guillemets
   visitor_id,variant,cart_value
   B001,control,"49,90"

✅ utiliser le point décimal
   visitor_id,variant,cart_value
   B001,control,49.90
```

---

## `GROUP_VALUE_NOT_FOUND`

Vous avez déclaré `A = "controle"` alors que la colonne contient `"control"`.

```
✗ Value "controle" not found in column `variant`

  Available values:
     control      2 410 rows
     treatment    2 398 rows
```

L'application n'applique **aucune correction orthographique automatique** : `"controle"` pourrait légitimement désigner un autre groupe. Choisissez dans la liste affichée.

---

## `EMPTY_GROUP`

```
✗ Group B is empty after exclusions

   B = "treatment"
   0 rows retained out of 2 398

   Most exclusions: MISSING_METRIC (2 398)
```

Presque toujours le signe que **la colonne métrique choisie n'est pas la bonne** — par exemple une colonne qui n'est renseignée que pour le groupe contrôle. Vérifiez votre sélection de colonne avant de suspecter vos données.

---

<a id="unsupported_metric"></a>
## `UNSUPPORTED_METRIC`

```
satisfaction
faible
moyen
élevé
```

```
✗ Metric column contains 3 distinct non-numeric values

  Supported metrics:
    · binary      — 2 distinct values
    · continuous  — numeric values
```

L'application ne traite pas les métriques ordinales. Deux issues :

- **Recoder en binaire** dans votre fichier (`élevé → 1`, le reste `→ 0`) et déclarer l'encodage ;
- **Choisir une autre colonne** de nature numérique.

---

## `ALL_ROWS_EXCLUDED`

```
✗ No rows left after exclusions

   n_input    = 4 820
   n_retained = 0

   MISSING_METRIC   4 820
```

Quand *toutes* les lignes tombent sur le même motif, la cause est structurelle et non liée à la qualité des données. Les deux origines les plus fréquentes :

- la mauvaise colonne a été sélectionnée comme métrique ;
- le fichier contient des décimales à la virgule non détectées, rendant chaque valeur non numérique.

---

## `CONTINUOUS_WITH_TWO_VALUES` *(avertissement)*

```
ℹ Metric declared as continuous, but only 2 distinct values found ({0, 1}).
  Binary methods (z-test, Fisher) are usually more appropriate.
  Continue anyway?
```

Ce n'est **pas** une erreur : calculer une moyenne sur des `0`/`1` est mathématiquement valide. Mais c'est presque toujours une déclaration involontaire. L'analyse se poursuit si vous confirmez, et l'avertissement est conservé dans le rapport.

---

## Liste de vérification avant import

```
☐ Un seul fichier, avec une ligne d'en-tête
☐ Une ligne = un participant
☐ Une colonne identifie le groupe, une colonne porte la métrique
☐ Encodage UTF-8
☐ Décimales : point, ou virgule avec un séparateur point-virgule
☐ Le mapping A = contrôle, B = nouveauté est vérifié
☐ Le type de métrique proposé a été confirmé, preuves regardées
☐ Le taux d'exclusion affiché est cohérent avec ce que vous attendiez
```

---

*Documents liés : `PLAN_DE_CODAGE.md` (étapes de développement) · `../Rapport_Conception_AB_Analysis_Workspace.md` (architecture et fondements statistiques).*
