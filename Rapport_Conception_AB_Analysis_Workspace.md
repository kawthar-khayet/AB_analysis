# Rapport de conception — A/B Analysis Workspace

**Projet** : construire un workspace local et reproductible transformant un jeu de données A/B en analyse fréquentiste complète.
**Date** : 1er septembre 2026
**Statut** : phase de conception — architecture et fondements statistiques. Aucun code écrit à ce stade.

---

## Table des matières

**Partie I — Cadrage**
1. Énoncé et lecture du projet
2. Le pipeline comme chaîne de transformations

**Partie II — Architecture technique**
3. Le principe des trois couches
4. Le contrat `StatisticalResult`
5. Décisions d'architecture actées
6. Conséquences techniques des décisions
7. Arborescence mise à jour

**Partie III — Fondements statistiques**
8. Pourquoi un test statistique est nécessaire
9. La p-value
10. L'estimé B−A
11. L'intervalle de confiance
12. Le catalogue des méthodes
13. La taille d'effet

**Partie IV — Synthèse**
14. Les trois questions de la page Results
15. Arbre de décision du module d'interprétation
16. Ordre d'implémentation recommandé
17. Points ouverts et prochaines étapes

---

# Partie I — Cadrage

## 1. Énoncé et lecture du projet

### Énoncé du professeur

> Build a local, reproducible workspace that transforms an A/B dataset into a complete frequentist analysis: simulate/import data → validate and inspect diagnostics → configure a statistical method → quantify effect and uncertainty → interpret the result → export a report.

### Document de référence

Le document `AB_Analysis_Workspace_Project_Architecture.pdf` est une **proposition d'architecture rédigée par l'étudiante**, et non une consigne du professeur. Il est donc négociable : les seules contraintes réelles viennent de l'énoncé ci-dessus. Ce rapport en reprend les bonnes idées, en corrige les incohérences et en tranche les ambiguïtés.

### Ce que l'application est réellement

L'application **n'est pas un calculateur de p-value**. Le calcul statistique représente environ 15 % du code. Le reste est de la **traçabilité** : ce qui a été exclu, ce qui est douteux, avec quelle graine aléatoire, sous quelles hypothèses de validité.

C'est un objet qui transporte **une décision et sa justification** d'un bout à l'autre du pipeline.

---

## 2. Le pipeline comme chaîne de transformations

Chaque étape prend un objet et en produit un autre :

```
CSV / simulation   →  Dataset validé
Dataset validé     →  Configuration d'analyse   (qui est A, qui est B, quelle métrique)
Configuration      →  Diagnostics               (ces données sont-elles exploitables ?)
Configuration      →  Méthode choisie           (quel test, avec quelles hypothèses)
Méthode + données  →  StatisticalResult         (le résultat chiffré)
StatisticalResult  →  Interprétation            (la phrase en français)
StatisticalResult  →  Rapport exporté
```

| Étape | Action utilisateur / système | Sortie principale |
|---|---|---|
| 1. Data | Simuler une expérience binaire/continue ou importer un CSV | Dataset validé |
| 2. Mapping | Désigner explicitement Contrôle A, Traitement B et une métrique | Configuration d'analyse |
| 3. Diagnostics | Effectifs, valeurs manquantes, statistiques descriptives, graphiques | Vue qualité des données |
| 4. Method | L'analyste choisit une méthode compatible ; l'UI expose hypothèses et warnings | Test configuré |
| 5. Analysis | Calcul de l'estimé B−A, IC, p-value, taille d'effet, décision | `StatisticalResult` |
| 6. Interpretation | Interprétation déterministe et prudente ; significativité ≠ importance pratique | Conclusion lisible |
| 7. Export | Export des données/résultats et rapport PDF | Artefact reproductible |

---

# Partie II — Architecture technique

## 3. Le principe des trois couches

> **The statistics package owns every scientific calculation and must not import FastAPI or React.**

C'est le principe fondateur de l'architecture.

```
                     Analyste
                        │
              React + Vite Workspace
                        │  HTTP / JSON
                        ▼
                FastAPI API (/api/v1)
                        │
                        ├── schémas Pydantic requête/réponse
                        ├── services analyse / export
                        └── validation + erreurs structurées
                        │
                        ▼
        Package Python de statistiques (framework-independent)
                        │
                        ├── normalisation des données & diagnostics
                        ├── méthodes statistiques
                        ├── intervalles de confiance / tailles d'effet
                        ├── règles d'interprétation
                        └── contrat commun StatisticalResult
                        │
                        ▼
                NumPy / SciPy / Statsmodels
```

### Règle de dépendance

| Couche | Ce qu'elle connaît | Ce qu'elle ne doit **jamais** connaître |
|---|---|---|
| `ab_stats` | NumPy, SciPy, des listes de nombres | HTTP, JSON, Pydantic, requêtes, React |
| `backend` | `ab_stats`, Pydantic, FastAPI | les formules statistiques |
| `frontend` | l'API JSON | les formules statistiques |

### Pourquoi cela compte

Au-delà de la propreté : le package `ab_stats` devient **testable sans lancer de serveur**. Les résultats peuvent être comparés à SciPy dans un simple test unitaire. Si une formule est fausse, un test la détecte — pas un clic dans une interface. Pour un projet évalué sur la justesse scientifique, c'est décisif.

**Corollaire souvent négligé : le frontend n'a pas le droit de recalculer.** Si React a besoin de la borne basse de l'IC pour dessiner une barre d'erreur, elle doit venir de l'API. Sinon deux sources de vérité divergent.

---

## 4. Le contrat `StatisticalResult`

Toutes les méthodes retournent **la même structure** : hypothèses, statistique, p-value, alpha, estimé B−A, intervalle de confiance, taille d'effet, décision, hypothèses de validité, warnings, métadonnées de reproductibilité.

### Pourquoi un contrat unique

Fisher exact, Welch et le bootstrap sont mathématiquement très différents. Mais s'ils retournent le même objet :

- la page Results en React est écrite **une seule fois** et fonctionne pour les 7 méthodes ;
- l'export PDF est écrit **une seule fois** ;
- ajouter une 8ᵉ méthode plus tard ne casse rien en aval.

### Le prix à payer

Certains champs seront `null` selon la méthode :

- **Fisher exact** n'a pas de « statistique de test » au sens classique, et ne produit pas naturellement un IC sur la *différence de taux* (il donne un IC sur l'*odds ratio*).
- **Bootstrap** produit naturellement un IC, mais pas une p-value.
- **Mann-Whitney** ne produit pas une différence de moyennes.

Ce choix doit être **assumé et documenté explicitement**, pas caché.

---

## 5. Décisions d'architecture actées

### Décision A — Backend *stateless*, dataset conservé côté navigateur

**Décision retenue :** pas de `dataset_id`, pas de registre en mémoire côté serveur. Le frontend conserve le dataset pendant tout le workflow et l'envoie au backend lorsque nécessaire.

**Justification :** un backend sans état colle exactement au principe de reproductibilité du projet. Chaque requête est **auto-descriptive** — elle contient les données, la méthode, l'alpha, la graine. Rien n'est caché côté serveur, et n'importe quelle requête peut être rejouée à l'identique six mois plus tard. Avec un registre en mémoire, le résultat aurait dépendu d'un état serveur invisible et volatil.

**Bénéfice secondaire :** élimine toute une classe de problèmes — expiration de sessions, nettoyage mémoire, collisions entre utilisateurs, perte d'état au redémarrage, `dataset_id` inconnu.

### Décision B — Layout en atelier

Coquille persistante : sidebar de navigation + zone de travail.

```
┌──────────────────────────────────────────────────────────┐
│  A/B Analysis Workspace          dataset: exp_042 · n=4820│
├───────────────┬──────────────────────────────────────────┤
│ ✓ Dataset     │                                          │
│ ✓ Diagnostics │            [ zone de travail ]           │
│ ● Method      │         (contenu de l'étape active)      │
│ ○ Results     │                                          │
│ ○ Export      │                                          │
└───────────────┴──────────────────────────────────────────┘
   ✓ fait   ● en cours   ○ pas encore accessible
```

Cette décision tranche une incohérence du PDF initial : la section 6 listait **5** pages (Dataset, Diagnostics, Method, Results, Export) alors que la structure de dossiers n'en déclarait que **4** (pas de `Export.tsx`). **Export est bien une 5ᵉ page.**

### Décision C — Navigation libre, application guidante

**Décision retenue :** toutes les entrées de la sidebar sont cliquables à tout moment. L'analyste n'est jamais bloqué. Les pages dont les prérequis manquent affichent une explication et un chemin, au lieu d'être grisées.

C'est le prolongement du principe *« never silently »* du projet : ne jamais bloquer en silence non plus — toujours dire pourquoi.

```
┌────────────────────────────────────────────┐
│  Aucun jeu de données chargé               │
│                                            │
│  Les diagnostics nécessitent un dataset    │
│  et un mapping de colonnes.                │
│                                            │
│              [ Aller à Dataset → ]         │
└────────────────────────────────────────────┘
```

La sidebar garde ses indicateurs ✓ / ● / ○ comme **information d'avancement**, sans jamais interdire.

### Décision D — Le choix de la méthode n'est jamais automatique

> *Never silently choose a statistical test.*

L'application propose les méthodes compatibles, affiche leurs hypothèses de validité et ses avertissements. **L'analyste choisit.** Cela impose un composant que le PDF initial ne nommait pas : un **moteur de compatibilité** (voir §12).

### Décision E — L'interprétation est un système de règles déterministe

« Deterministic, cautious interpretation » = un arbre de décision codé en dur. Pas d'IA, pas de hasard : deux exécutions identiques produisent mot pour mot la même phrase.

---

## 6. Conséquences techniques des décisions

### 6.1 `/datasets/import` devient un endpoint de validation, pas de stockage

Il ne range plus rien. Il reçoit un CSV, le valide, le normalise, et **renvoie** au navigateur les données propres accompagnées du rapport de validation (lignes exclues et motif, types détectés, valeurs manquantes). Le frontend conserve ce retour.

Même logique pour `/simulations` : il renvoie les données générées **et la graine utilisée**.

### 6.2 Règle non négociable : revalidation à chaque appel

Puisque les données transitent par le navigateur, elles peuvent avoir été modifiées entre-temps. **Le backend ne doit jamais supposer qu'un payload est déjà validé** sous prétexte qu'il est passé par `/import`. Chaque endpoint recevant des données les revérifie.

### 6.3 Envoyer les colonnes, pas le CSV

Une fois le mapping effectué, l'analyse n'a besoin que de **deux colonnes**. Inutile de retransporter un fichier complet avec ses 30 colonnes inutiles.

```json
{
  "group":  ["A", "A", "B", "A", "B"],
  "metric": [0, 1, 1, 0, 1],
  "metric_type": "binary"
}
```

Format colonnaire, deux tableaux parallèles. Prévoir une **limite de taille explicite** (par exemple 100 000 lignes) refusée proprement avec un message clair.

### 6.4 État de session côté frontend

Composant absent du PDF initial, indispensable avec une sidebar. Un objet unique partagé par les 5 pages :

```
WorkspaceState
  ├── dataset            (données validées, conservées dans le navigateur)
  ├── validationReport   (exclusions, types détectés, valeurs manquantes)
  ├── mapping            (colonne groupe, valeur A, valeur B, colonne métrique)
  ├── diagnostics        (dernier résultat de diagnostics)
  ├── selectedMethod     (+ alpha, seed, paramètres)
  └── result             (dernier StatisticalResult)
```

La sidebar lit cet objet pour afficher ses ✓ / ● / ○ et l'en-tête `dataset: exp_042 · n=4820`.

**Règle :** cet état **stocke** ce que l'API a renvoyé, il ne **recalcule** jamais rien.

**Persistance :** un `sessionStorage` sur `WorkspaceState` évite qu'un simple F5 fasse tout perdre. Attention au quota (~5 Mo) pour les gros datasets.

### 6.5 Contrat d'API

| Endpoint | Rôle |
|---|---|
| `POST /api/v1/datasets/import` | Valide et normalise un CSV, **renvoie** les données propres + rapport |
| `POST /api/v1/simulations` | Génère des données A/B déterministes (+ graine) |
| `POST /api/v1/diagnostics` | Qualité des données + statistiques descriptives |
| `POST /api/v1/analyses` | Exécute la méthode sélectionnée → `StatisticalResult` |
| `GET  /api/v1/methods` | Liste des méthodes + compatibilité métrique + hypothèses |
| `POST /api/v1/exports/pdf` | Génère le rapport d'analyse |
| `GET  /api/v1/health` | Health check |

---

## 7. Arborescence mise à jour

```
ab-analysis-workspace/
├── packages/
│   └── ab_stats/
│       ├── data.py                  # normalisation / validation
│       ├── diagnostics.py           # résumés et diagnostics
│       ├── results.py               # contrat StatisticalResult
│       ├── methods/
│       │   ├── proportions.py
│       │   ├── ttests.py
│       │   ├── mann_whitney.py
│       │   ├── permutation.py
│       │   └── bootstrap.py
│       ├── effect_sizes.py
│       ├── confidence_intervals.py
│       ├── compatibility.py         # AJOUT : moteur de compatibilité
│       ├── interpretation.py
│       └── tests/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   ├── datasets.py
│   │   │   ├── analyses.py
│   │   │   └── exports.py
│   │   └── services/
│   │       ├── analysis_service.py
│   │       └── export_service.py
│   └── tests/
├── frontend/
│   └── src/
│       ├── layout/
│       │   ├── WorkspaceLayout.tsx  # AJOUT : sidebar + zone de travail
│       │   └── StepNav.tsx          # AJOUT : les 5 entrées et leur état
│       ├── pages/
│       │   ├── Dataset.tsx          # renommé depuis Data.tsx
│       │   ├── Diagnostics.tsx
│       │   ├── Method.tsx           # renommé depuis Analysis.tsx
│       │   ├── Results.tsx
│       │   └── Export.tsx           # AJOUT : 5e page
│       ├── state/
│       │   └── workspaceState.ts    # AJOUT : état de session
│       ├── components/
│       ├── api/
│       └── types/
├── examples/
├── docs/
├── docker-compose.yml
└── README.md
```

Modifications par rapport au PDF initial : ajout de `compatibility.py`, `Export.tsx`, du dossier `layout/` et de `state/` ; renommage de `Data.tsx` → `Dataset.tsx` et `Analysis.tsx` → `Method.tsx` pour aligner les noms de fichiers sur les étapes de la sidebar.

---

# Partie III — Fondements statistiques

> Cette partie constitue le socle scientifique du projet. Chaque notion y est reliée à une décision de conception concrète.

## 8. Pourquoi un test statistique est nécessaire

### Le scénario de référence

Utilisé dans tout le rapport : test d'un nouveau bouton d'achat.

```
Groupe A (ancien bouton) :  1 000 visiteurs,  111 achats  →  11,1 %
Groupe B (nouveau bouton):  1 000 visiteurs,  124 achats  →  12,4 %
```

B est devant de 1,3 point. Ces chiffres sont exacts. Pourquoi ne pas conclure « B est meilleur » ?

### Le piège : on ne s'intéresse pas à ces 2 000 personnes

Ces 2 000 visiteurs sont déjà passés, leurs achats sont faits. Ce qu'on veut savoir, c'est **ce qui se passera avec les prochains millions de visiteurs**, puisqu'il faudra décider de déployer ou non.

Ces 2 000 personnes sont donc un **échantillon** — un tirage au sort parmi tous les visiteurs possibles. Et un tirage au sort, ça bouge.

### L'expérience de pensée décisive : le test A/A

Si l'on montrait **exactement le même bouton** à 2 000 personnes réparties au hasard en deux groupes A et B, on n'obtiendrait pas 11,1 % contre 11,1 %. On obtiendrait peut-être 10,8 % et 11,5 %. Ou 11,9 % et 10,4 %.

**Un écart apparaît alors qu'il n'y a rien à trouver.** C'est le hasard de la répartition.

Ce phénomène s'appelle la **variabilité d'échantillonnage**, et c'est l'adversaire contre lequel toute l'application est construite. (Le test A/A est réellement pratiqué en entreprise pour vérifier qu'une plateforme d'expérimentation ne raconte pas n'importe quoi.)

La vraie question n'est donc pas « B est-il devant ? », mais :

> **L'écart observé est-il plus grand que ce que le hasard seul produirait ?**

### Chiffrage du hasard

Avec 1 000 personnes par groupe autour de 11 %, l'amplitude typique du bruit sur l'écart vaut environ **1,4 point**. Un écart de ±2,8 points est donc parfaitement banal, même avec deux boutons identiques.

```
n = 1 000 par groupe
  bruit banal   ├──────────────────────────────┤   (−2,8 pp … +2,8 pp)
  écart observé            ▲ +1,3 pp
                → complètement noyé dans le bruit
```

Formulé autrement : la différence représente **13 achats** (124 contre 111). Treize personnes sur deux mille.

### Le même écart avec un échantillon 50 fois plus grand

```
Groupe A :  50 000 visiteurs,  5 550 achats  →  11,1 %
Groupe B :  50 000 visiteurs,  6 200 achats  →  12,4 %
```

```
n = 50 000 par groupe
  bruit banal        ├────┤                      (−0,4 pp … +0,4 pp)
  écart observé              ▲ +1,3 pp
                → très largement hors du bruit
```

Le bruit s'effondre à ±0,4 point ; l'écart est plus de six fois plus grand. Et concrètement, la différence n'est plus de 13 achats mais de **650 achats**.

### Le principe à retenir

> **Les pourcentages sont identiques dans les deux cas, et pourtant la conclusion est opposée.** Un chiffre observé ne signifie rien seul — il ne signifie quelque chose que **rapporté au bruit**, et le bruit dépend de la taille de l'échantillon.

**Conséquence de conception :** l'étape Diagnostics doit afficher les effectifs **avant** toute analyse. Sans `n`, un pourcentage est ininterprétable.

---

## 9. La p-value

### Définition

> La p-value est la probabilité d'observer un écart **au moins aussi extrême** que celui mesuré, **en supposant que H₀ est vraie**.

Le membre déterminant est **« en supposant que H₀ est vraie »**. La p-value se calcule *à l'intérieur* d'un monde imaginaire où B ne change rien. Toutes les erreurs d'interprétation viennent de là.

### Les trois notions associées

| Terme | Définition |
|---|---|
| **H₀ (hypothèse nulle)** | La posture du sceptique : « les deux variantes sont identiques, tout écart n'est que du bruit ». On ne cherche jamais à prouver que B est meilleur ; on cherche à montrer que H₀ n'explique plus ce qu'on observe. |
| **p-value** | La mesure de la surprise, sous H₀. |
| **α (alpha)** | Le seuil de surprise fixé **avant** de regarder les données (typiquement 0,05). Convention de décision, pas vérité mathématique. |

### Le mécanisme en trois temps

**Temps 1 — construire le monde de H₀.** On suppose les deux boutons identiques et on établit la distribution des écarts produits par le pur hasard (centrée sur 0, amplitude typique 1,4 point pour n = 1 000).

**Temps 2 — y placer l'écart observé.**

```
      distribution des écarts SI H₀ était vraie  (n = 1 000)

                        ▁▂▄▆████████▆▄▂▁
        ────┬───────────────────┬──┬───────────────────┬────
          −2,8                  0  │                 +2,8
                                   ▲ écart observé : +1,3
```

**Temps 3 — mesurer la surface des queues** au-delà de ±1,3. Cette surface est la p-value : ici **≈ 0,37**.

### Ce que « 37 % des expériences » signifie concrètement

On imagine 100 répétitions de l'expérience avec des boutons **rigoureusement identiques** (H₀ vraie, donc rien à trouver). À chaque répétition on note l'écart B−A :

```
   écart B−A          nombre d'expériences (sur 100)

   −4 à −3 pp   ▪                                        1
   −3 à −2 pp   ▪▪▪▪▪▪                                   6
   −2 à −1 pp   ▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪                        16
   −1 à  0 pp   ▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪              26
    0 à +1 pp   ▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪              26
   +1 à +2 pp   ▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪                        16
   +2 à +3 pp   ▪▪▪▪▪▪                                   6
   +3 à +4 pp   ▪                                        1
```

Le hasard seul produit couramment des écarts de 1, 2, voire 3 points, **sans aucune différence réelle**.

On compte ensuite tout ce qui dépasse ±1,3 : environ **37 expériences sur 100**.

> Sur 100 mondes où les boutons sont identiques, 37 auraient donné un écart aussi spectaculaire. Le résultat n'a donc rien de remarquable : c'est ce que le hasard fabrique un tiers du temps.

Par comparaison, p = 0,001 signifierait qu'il faudrait **1 000** répétitions pour en voir une comme la nôtre.

### Deux précisions de construction

- **« Au moins aussi grand », pas « exactement égal ».** On mesure une *queue* de distribution, pas un point : la probabilité de tomber exactement sur +1,3000… est essentiellement nulle. Ce qui informe, c'est la distance au centre, donc une surface.
- **On compte les deux côtés** (test **bilatéral**), parce qu'avant l'expérience on ignorait le sens de l'effet et qu'un écart de −1,3 aurait tout autant intrigué. En unilatéral on obtiendrait p = 0,18, deux fois moins. **Ce choix doit être fait avant de voir les données** et doit être un paramètre explicite de la page Method.

### Le pont avec le code

Cette expérience imaginaire est **réellement exécutée** par `permutation.py` : mélanger au hasard les étiquettes A et B des milliers de fois détruit toute vraie différence et fabrique un monde où H₀ est vraie. Le t-test et le z-test, eux, ne simulent rien : ils *calculent* cette distribution par une formule, plus rapide mais au prix d'hypothèses.

### Les trois interprétations fausses

#### ❌ 1. « p = 0,03, donc il y a 3 % de chances que H₀ soit vraie »

**Inversion de conditionnelle.** La p-value donne :

> probabilité **des données**, *sachant que* H₀ est vraie

et elle est lue comme :

> probabilité **de H₀**, *sachant* les données

Analogie : la probabilité d'être mouillé sachant qu'il pleut est proche de 100 % ; la probabilité qu'il pleuve sachant qu'on est mouillé est bien plus faible — on sort peut-être de la douche.

Le cadre fréquentiste **ne peut pas** donner la probabilité que H₀ soit vraie. (Le cadre bayésien le peut, mais ce n'est pas ce projet.)

#### ❌ 2. « p = 0,37 > 0,05, donc A et B sont équivalents »

Ne pas avoir trouvé de preuve n'est pas une preuve d'absence. Avec n = 1 000, le test était **aveugle** : il ne pouvait pas distinguer 1,3 point du bruit. Avec le même écart et n = 50 000, l'effet apparaît nettement.

Formulation correcte : **« les données ne fournissent pas de preuve suffisante d'un effet »**.

#### ❌ 3. « p = 0,0000001, donc l'effet est important »

La p-value mélange **l'ampleur de l'effet et la taille de l'échantillon**. Avec 10 millions d'utilisateurs, un écart de 0,01 point — économiquement nul — sortira avec une p-value écrasante.

Une p-value répond à « est-ce du bruit ? ». Jamais à « est-ce que ça vaut le coup ? ».

### L'analogie du procès

**H₀ = la présomption d'innocence.**

- La p-value mesure à quel point les preuves seraient improbables **si l'accusé était innocent**.
- α est le niveau d'exigence du tribunal.
- `p < α` → « coupable au-delà du doute raisonnable ». On **rejette** H₀.
- `p > α` → **acquittement, pas innocence.** « Pas assez de preuves » inclut parfaitement « coupable mais dossier trop mince ».

Le tribunal ne dit jamais « il y a 3 % de chances qu'il soit innocent ».

### Règles de conception qui en découlent

1. **Ne jamais afficher une p-value seule** — toujours avec l'estimé B−A, l'IC et la taille d'effet.
2. **Vocabulaire de décision fermé** :

```
"reject_null"          → preuve suffisante contre H₀
"fail_to_reject_null"  → preuve insuffisante
```

Jamais `"accept_null"`, jamais `"no_difference"`. **Si le mot n'existe pas dans l'enum, personne ne pourra l'afficher** — c'est la garantie structurelle contre l'erreur n° 2.

3. **Deux branches distinctes dans le module d'interprétation.** Le cas non significatif n'est pas « le contraire » du cas significatif : il a sa propre phrase, prudente.
4. **α est enregistré dans le résultat et fixé à l'avance**, ce qui empêche d'ajuster le seuil après coup.
5. **Détail d'affichage :** jamais `p = 0.000`, mais `p < 0,001`. Une p-value n'est jamais exactement nulle.

---

## 10. L'estimé B−A

### Définition

C'est **la différence mesurée entre les deux groupes**, dans un sens fixé une fois pour toutes.

```
métrique binaire    →  taux(B) − taux(A)        =  12,4 % − 11,1 %    =  +1,3 pp
métrique continue   →  moyenne(B) − moyenne(A)  =  47,20 € − 45,10 €  =  +2,10 €
```

C'est la réponse à **« de combien ? »** — la question que la p-value ne traite pas.

On parle d'**estimation ponctuelle** : *ponctuelle* car c'est un seul nombre, *estimation* car c'est une mesure bruitée d'une vraie valeur inconnue. D'où la nécessité de l'accompagner d'un intervalle de confiance.

### Pourquoi « toujours B − A »

> *Keep the effect direction fixed as B − A.*

Si chaque méthode choisissait son sens, on obtiendrait tantôt +1,3 tantôt −1,3 pour la même expérience. Conséquences :

- le module d'interprétation ne peut plus raisonner sur le signe, alors que c'est toute son utilité (`estimate > 0` doit **toujours** signifier « B fait mieux ») ;
- l'analyste ne peut plus comparer deux méthodes entre elles.

**Règle : A est la référence, B est la nouveauté, on soustrait toujours la référence.** Appliquée par les 7 méthodes, sans exception.

### Le piège d'unité

Deux façons exactes de dire « B est meilleur », qui ne donnent pas le même nombre :

```
différence absolue  :  12,4 % − 11,1 %          =  +1,3 point de pourcentage
différence relative :  (12,4 − 11,1) / 11,1     =  +11,7 %
```

« Le bouton améliore la conversion de 1,3 % » et « de 11,7 % » ne racontent pas la même histoire à un décideur — source classique d'exagération dans les rapports.

**Conséquence de conception :** le champ `estimate` doit porter **son unité explicitement** (`percentage_points`, `euros`, `seconds`…) et l'interface ne doit jamais écrire un `%` ambigu. L'estimé du contrat, celui qui sert aux calculs et à l'IC, reste **l'absolu** ; le lift relatif va dans un champ distinct.

### Cas particulier

Pour **Mann-Whitney**, il n'y a pas de différence de moyennes à donner (voir §12). L'estimé retenu est celui de **Hodges–Lehmann**.

---

## 11. L'intervalle de confiance

> Si la page Results ne devait afficher qu'**une** chose, ce serait celle-là.

### Construction

```
IC 95 %  =  estimé  ±  ( 1,96 × bruit typique )
              ↑              ↑
        ce que tu as    ce que tu as calculé
          mesuré        pour la p-value
```

Le `1,96` correspond au niveau 95 %. Le bruit est le même que celui de la p-value : **l'IC et la p-value sont deux lectures du même calcul**.

### Sur le scénario de référence

```
n = 1 000       estimé +1,3 pp   bruit 1,44   →  1,3 ± 2,82  →  [−1,5 ; +4,1] pp
n = 50 000      estimé +1,3 pp   bruit 0,20   →  1,3 ± 0,40  →  [+0,90 ; +1,70] pp
```

```
                    0
                    ┆
   n = 1 000        ┆
           ├────────┼───────●────────────────┤
         −1,5             +1,3            +4,1
                    ┆
   n = 50 000       ┆
                    ┆    ├──●──┤
                       +0,90 +1,70
```

- **n = 1 000** → « le vrai effet est entre −1,5 et +4,1 points ». Le nouveau bouton pourrait être nettement meilleur **ou franchement pire**. On ne sait rien.
- **n = 50 000** → « le vrai effet est entre +0,90 et +1,70 point ». Le bouton est meilleur, et on sait de combien à un demi-point près.

### Lien avec la p-value

Le premier intervalle **contient 0** — or 0 signifie « aucune différence », c'est-à-dire H₀. H₀ reste plausible → non significatif (p = 0,37). Le second **exclut 0** → significatif.

> **Règle générale : un IC à 95 % qui contient 0 ⟺ p > 0,05.** Les deux disent la même chose, mais l'IC dit **en plus** de combien.

> ⚠️ **Piège d'implémentation.** Pour le test de deux proportions, la p-value se calcule classiquement avec une variance « poolée » (groupes fusionnés sous H₀) et l'IC avec une variance non poolée. Dans des cas limites, on peut donc obtenir p = 0,049 avec un IC contenant 0 de justesse. Ce n'est pas un bug mais une incohérence connue entre deux conventions. Le `StatisticalResult` doit soit documenter la méthode de calcul de l'IC, soit lever un warning en cas de contradiction — plutôt qu'afficher deux nombres qui se disputent.

### L'interprétation exacte

❌ **« Il y a 95 % de chances que le vrai effet soit entre +0,90 et +1,70 »**

Faux, pour la même raison que l'erreur n° 1 sur la p-value. Le vrai effet est une valeur **fixe** (inconnue mais fixe). Il est dans l'intervalle ou il n'y est pas.

✅ **Ce qui est aléatoire, c'est l'intervalle.** Le « 95 % » est une propriété de la *méthode* :

> Si je répétais l'expérience un grand nombre de fois en construisant un IC à chaque fois, **95 % de ces intervalles contiendraient la vraie valeur.**

```
   vraie valeur (inconnue)
             ┆
   exp.  1   ├──●──┤        ✓ contient
   exp.  2      ├──●──┤     ✓
   exp.  3  ├──●──┤         ✓
   exp.  4          ├──●──┤ ✗  raté
   exp.  5   ├──●──┤        ✓
   ...
             ┆
   sur 100 intervalles, environ 95 attrapent la vraie valeur
```

On ne saura jamais si le sien fait partie des 95 ou des 5. On sait seulement que la méthode se trompe une fois sur vingt.

### Pourquoi l'IC est supérieur à la p-value

Deux études **toutes deux non significatives** (p > 0,05) :

```
                    0
                    ┆
   Étude 1          ┆
                  ├─●─┤                    IC [−0,3 ; +0,5] pp
                    ┆
   Étude 2          ┆
           ├────────┼───────●────────────────┤   IC [−1,5 ; +4,1] pp
```

- **Étude 1** : « le vrai effet est au maximum d'un demi-point ». Conclusion **forte** : il n'y a pas d'effet important. On arrête.
- **Étude 2** : « le vrai effet est peut-être −1,5, peut-être +4,1 ». On n'a **rien appris**. L'étude était trop petite. Il faut relancer avec plus de trafic.

Même p-value, décisions opposées. C'est la justification du champ IC dans le contrat.

### Règles pour le contrat

1. **`confidence_level` est un champ enregistré** (0,95 par défaut), au même titre qu'`alpha`. Un IC sans son niveau ne veut rien dire.
2. **L'IC porte la même unité que l'estimé**, et le sens B−A reste fixe : `borne_basse < estimate < borne_haute`.

---

## 12. Le catalogue des méthodes

### Le principe qui explique tout

> **Chaque test achète sa précision en contractant un emprunt : des hypothèses sur les données.**

Plus un test suppose, plus il est puissant — mais plus il devient faux si les suppositions ne tiennent pas. Moins il suppose, plus il est robuste — mais il demande plus de données ou plus de calcul.

```
   beaucoup d'hypothèses                        peu d'hypothèses
   puissant, fragile                            robuste, gourmand
   ├────────────────────────────────────────────────────────────┤
   Student    Welch    z-test    Mann-Whitney   Permutation   Bootstrap
```

Il n'existe pas de « meilleur test », seulement **le test dont les hypothèses sont crédibles pour ces données** — ce que l'étape Diagnostics sert à établir. D'où l'ordre imposé Diagnostics → Method.

### Branche 1 : le type de métrique

```
                    métrique
                       │
        ┌──────────────┴──────────────┐
     BINAIRE                      CONTINUE
   0/1, oui/non                 €, secondes, nb de pages
   « a-t-il acheté ? »          « combien a-t-il dépensé ? »
        │                             │
   z-test 2 proportions          Student / Welch
   Fisher exact                  Mann-Whitney
                                 Permutation
                                 Bootstrap
```

Une donnée binaire ne peut pas être normale — elle ne prend que deux valeurs — et sa variance est **liée à sa moyenne** (`p(1−p)`). Les formules ne sont pas interchangeables.

**Première règle du moteur de compatibilité : proposer un t-test sur une métrique binaire doit être impossible**, pas seulement déconseillé.

### Famille binaire

#### `two_proportion_z_test` — le cheval de trait

Approxime la loi binomiale par une loi normale.

- **Hypothèses** : observations indépendantes, effectifs suffisants — règle usuelle : **au moins ~10 succès et ~10 échecs dans chaque groupe**.
- **Quand** : le cas standard du web.
- **Avantages** : rapide ; l'IC porte directement sur la différence de taux, qui est l'estimé B−A.
- **Casse quand** : événements rares (2 000 visiteurs, 3 conversions) — l'approximation normale ne tient plus et la p-value devient fausse.

#### `fisher_exact` — le test des petits effectifs

Aucune approximation : énumère toutes les répartitions possibles des succès et calcule la probabilité exacte.

- **Hypothèses** : quasiment aucune au-delà de l'indépendance.
- **Quand** : petits échantillons, événements rares.
- **Limites** : légèrement **conservateur** (p-values un peu trop grandes, donc conclut moins souvent) ; coûteux sur de très gros effectifs.
- **Piège pour le contrat** : ne fournit pas naturellement un IC sur la **différence de taux** (il donne un IC sur l'*odds ratio*). Il faut soit calculer l'IC de la différence autrement en le documentant, soit laisser le champ `null` avec un warning explicite.

> **Règle de compatibilité :** si un groupe a moins de 10 succès ou 10 échecs → warning sur le z-test, Fisher recommandé.

### Famille continue

#### `student_t_test` — le classique, et le plus fragile

- **Hypothèses** : normalité **et** variances égales.
- **Problème** : l'égalité des variances n'a presque jamais de justification. Un nouveau design peut produire la même moyenne avec une dispersion différente.
- **Recommandation** : le garder au catalogue pour la valeur pédagogique et la comparaison, mais **jamais comme choix par défaut**.

#### `welch_t_test` — le bon défaut

Même test, sans l'hypothèse d'égalité des variances (degrés de liberté ajustés).

- **Hypothèses** : normalité, ou grands échantillons via le théorème central limite.
- **Pourquoi c'est le défaut** : quand les variances sont égales, Welch ne perd presque rien face à Student ; quand elles ne le sont pas, il protège. Le rapport bénéfice/risque est asymétrique.

> ⚠️ **Mauvaise pratique répandue, à ne pas coder** : faire d'abord un test d'égalité des variances (Levene, F-test) puis choisir Student ou Welch selon le résultat. Cette procédure en deux temps **fausse les taux d'erreur** du test final, car la décision dépend elle-même des données. La bonne approche : **choisir Welch d'avance**. C'est cohérent avec *« never silently choose a statistical test »* — l'application recommande, l'analyste décide, mais aucun pré-test automatique ne branche à sa place.

**Sur la normalité :** les t-tests y sont assez robustes dès que `n` est grand (quelques centaines). Ce qui les casse vraiment, c'est une **forte asymétrie combinée à un petit échantillon**, ou des **valeurs extrêmes** (un client à 12 000 € parmi des clients à 40 € fait exploser moyenne et variance). C'est le déclencheur du warning vers Mann-Whitney ou la permutation.

#### `mann_whitney_u` — le test des rangs

Jette les valeurs et ne garde que **l'ordre** : classe toutes les observations des deux groupes confondus et compare les rangs.

- **Hypothèses** : indépendance, métrique au moins ordinale. Pas de normalité.
- **Quand** : distributions très asymétriques, valeurs extrêmes, données ordinales (notes 1–5), petits échantillons non normaux.
- **⚠️ Subtilité majeure** : Mann-Whitney **ne compare ni les moyennes ni les médianes**. Il teste :

  > « si je tire un utilisateur au hasard dans B et un dans A, la probabilité que celui de B ait la plus grande valeur diffère-t-elle de 50 % ? »

  On ne peut le lire comme une comparaison de **médianes** qu'en ajoutant l'hypothèse que les deux distributions ont la **même forme** et ne diffèrent que par un décalage. Cette hypothèse doit figurer dans le champ `assumptions`.

- **Estimé B−A retenu** : l'**estimateur de Hodges–Lehmann** — la médiane de toutes les différences par paires entre une valeur de B et une valeur de A. Il possède un IC associé, il est dans l'unité de la métrique et il respecte le sens B−A.

#### `permutation_test` — la machine à p-values

Exécute réellement l'expérience de pensée : mélange au hasard les étiquettes A et B des milliers de fois, recalcule l'écart des moyennes à chaque mélange, compte combien dépassent l'écart observé.

- **Hypothèses** : l'**échangeabilité** sous H₀ — une observation aurait tout aussi bien pu tomber dans l'autre groupe. Pas de normalité, pas de forme imposée.
- **Avantages** : conceptuellement transparent, c'est la définition même de la p-value.
- **Coûts** : lent ; **exige une graine aléatoire** pour la reproductibilité.
- **Nuance à documenter** : la permutation est *exacte* pour l'hypothèse « les deux groupes suivent la même distribution ». Pour l'hypothèse plus étroite « les deux moyennes sont égales » avec des variances différentes, elle n'est qu'approximative.

#### `bootstrap_difference` — la machine à intervalles

Principe inverse : on ne détruit pas l'effet, on **rééchantillonne chaque groupe avec remise** des milliers de fois pour mesurer l'instabilité de l'estimé B−A.

- **Hypothèses** : peu, mais l'échantillon doit être assez grand pour être représentatif (peu fiable en dessous de ~30 par groupe).
- **Produit naturellement** : un **IC** (percentiles 2,5 % et 97,5 % des rééchantillonnages). Pas de p-value native.
- **Exige une graine.**

#### Pourquoi les deux méthodes de rééchantillonnage

```
   permutation  →  répond « est-ce du bruit ? »      (p-value native)
   bootstrap    →  répond « de combien ? »           (IC natif)
```

Ce ne sont pas deux versions du même outil, mais les deux moitiés de la page Results obtenues sans formule paramétrique.

### Tableau récapitulatif

| Méthode | Métrique | Hypothèses clés | À utiliser quand | `estimate` (B−A) |
|---|---|---|---|---|
| `two_proportion_z` | binaire | indépendance, ≥ ~10 succès **et** ~10 échecs par groupe | cas standard du web | différence de taux |
| `fisher_exact` | binaire | indépendance | petits effectifs, événements rares | diff. de taux (IC à documenter) |
| `student_t` | continue | normalité + **variances égales** | référence pédagogique | diff. de moyennes |
| `welch_t` | continue | normalité (ou grand `n`) | **défaut recommandé** | diff. de moyennes |
| `mann_whitney_u` | continue / ordinale | indépendance ; même forme si lecture en médianes | asymétrie forte, valeurs extrêmes | Hodges–Lehmann |
| `permutation` | continue | échangeabilité sous H₀ ; **graine** | peu d'hypothèses, p-value transparente | diff. de moyennes |
| `bootstrap` | continue | échantillon représentatif, `n` pas trop petit ; **graine** | IC sans hypothèse de forme | diff. de moyennes |

### Le moteur de compatibilité

Alimente `GET /api/v1/methods` et la page Method. Il prend le **type de métrique + les diagnostics** et renvoie, pour chaque méthode : `compatible` (oui/non), `assumptions`, `warnings`.

Trois niveaux à ne pas confondre :

```
INCOMPATIBLE  →  la méthode ne peut pas s'appliquer, elle n'apparaît pas
                 ex. t-test sur métrique binaire

WARNING       →  applicable, mais une hypothèse est douteuse
                 ex. z-test avec 4 succès dans le groupe A
                 → proposée, signalée, avec l'alternative suggérée

OK            →  hypothèses plausibles au vu des diagnostics
```

Les warnings doivent être **machine-readable**, pas des chaînes libres :

```json
{
  "code": "LOW_EVENT_COUNT",
  "severity": "warning",
  "message": "Le groupe A ne compte que 4 succès (minimum recommandé : 10).",
  "affected_methods": ["two_proportion_z"],
  "suggested_alternative": "fisher_exact"
}
```

Un code stable permet à React d'afficher une icône, de traduire, de filtrer. Une phrase libre ne permet rien de tout cela.

**Déclencheurs à prévoir :** `LOW_EVENT_COUNT`, `SMALL_SAMPLE`, `HIGH_SKEWNESS`, `OUTLIERS_DETECTED`, `UNEQUAL_VARIANCES`, `ZERO_VARIANCE`, `UNBALANCED_GROUPS`, `MISSING_VALUES_EXCLUDED`.

---

## 13. La taille d'effet

### Le problème qu'elle résout

L'estimé B−A est exprimé dans **l'unité de la métrique** : `+2,10 €`. Est-ce beaucoup ? Impossible de répondre sans savoir à quel point les paniers varient naturellement.

```
   σ = 1 €   (paniers très homogènes)
         A              B
       ▁▄█▄▁          ▁▄█▄▁
    ───────────────────────────────►  €
    les deux groupes sont presque disjoints : +2,10 € est énorme


   σ = 40 €  (paniers très dispersés)
                  A ≈ B
            ▁▂▄▆████████▆▄▂▁
    ───────────────────────────────►  €
    les deux groupes se superposent presque : +2,10 € est noyé
```

> **La taille d'effet, c'est la différence exprimée en unités de variabilité naturelle**, plutôt qu'en euros ou en points. Elle est **sans unité**, donc comparable entre des expériences qui n'ont rien à voir.

### Métriques continues : le `d` de Cohen

```
        moyenne(B) − moyenne(A)        estimé B−A
   d = ─────────────────────────  =  ──────────────
            écart-type commun            variabilité
```

`d = 0,5` signifie « les deux moyennes sont séparées d'un demi écart-type ». Dans les deux dessins ci-dessus : `d = 2,1` puis `d = 0,05`.

**Repères conventionnels de Cohen :**

```
   |d| ≈ 0,2   petit
   |d| ≈ 0,5   moyen
   |d| ≈ 0,8   grand
```

**Deux raffinements :**

- Le **`g` de Hedges** — le `d` surestime légèrement l'effet sur de petits échantillons ; `g` applique une correction. À privilégier quand `n` est faible.
- **Avec Welch**, l'« écart-type commun » est douteux par construction. On utilise alors souvent l'écart-type du **groupe contrôle** seul (*delta de Glass*). À documenter dans `assumptions`.

### Métriques binaires : le `h` de Cohen

Le même `+1 pp` ne vaut pas la même chose selon l'endroit de l'échelle, car la variabilité d'une proportion dépend de sa valeur (`p(1−p)`, maximale à 50 %, minuscule près de 0 ou 100 %) :

```
   1,0 %  →  2,0 %      le taux a DOUBLÉ
  50,0 %  → 51,0 %      variation anecdotique
```

Le `h` de Cohen corrige cela par une transformation arcsinus qui redresse l'échelle :

```
   1 % → 2 %      h ≈ 0,084
  50 % → 51 %     h ≈ 0,020        quatre fois moins, pour le même +1 pp
```

C'est pourquoi le `d` ne s'applique pas au binaire, et pourquoi le catalogue doit associer **une mesure d'effet à chaque méthode**.

### Mann-Whitney : le delta de Cliff

Puisque Mann-Whitney raisonne sur des rangs, sa mesure d'effet naturelle aussi :

```
   δ = P(une valeur de B > une valeur de A) − P(une valeur de A > une valeur de B)
```

Varie de −1 (tout B en dessous) à +1 (tout B au-dessus), vaut 0 quand les groupes sont indiscernables. C'est **littéralement ce que Mann-Whitney teste**, exprimé comme une amplitude.

### L'avertissement le plus important

Sur le scénario de référence avec n = 50 000 :

```
   11,1 %  →  12,4 %
   p ≈ 0,0000000002        ultra significatif
   IC 95 % : [+0,90 ; +1,70] pp
   h ≈ 0,04                « effet négligeable » selon Cohen
   en pratique : +650 achats sur 50 000 visiteurs
```

**Un effet statistiquement écrasant, une taille d'effet « négligeable », et une valeur économique énorme — les trois à la fois, sans contradiction.**

C'est le quotidien de l'A/B testing web : les vrais effets y sont presque toujours en dessous du seuil « petit » de Cohen et pèsent pourtant des millions. Les repères 0,2 / 0,5 / 0,8 viennent de la psychologie expérimentale des années 1970 ; ce sont des **conventions**, pas des lois de la nature.

**Conséquence de conception :** ne jamais afficher l'étiquette « effet négligeable » comme un verdict. Si elle est affichée, la marquer explicitement comme *« convention de Cohen »* et la garder **séparée** du seuil de pertinence pratique δ fixé par l'analyste. C'est δ, pas Cohen, qui décide s'il vaut la peine de déployer.

### Conséquence pour le contrat

La mesure changeant selon la méthode, `effect_size` ne peut pas être un simple nombre :

```json
{
  "effect_size": {
    "name": "cohens_h",
    "value": 0.0403,
    "convention": "cohen_1988",
    "label": "small"
  }
}
```

Le champ `label` est optionnel et ne doit jamais être présenté comme un jugement.

**Appariement méthode ↔ mesure d'effet :**

| Méthode | Mesure d'effet |
|---|---|
| `two_proportion_z`, `fisher_exact` | `cohens_h` |
| `student_t`, `welch_t`, `permutation`, `bootstrap` | `cohens_d` (ou `hedges_g` si petit `n`) |
| `mann_whitney_u` | `cliffs_delta` |

Le **lift relatif** (`+11,7 %`) peut être affiché à côté car c'est le langage des décideurs, mais ce n'est pas une taille d'effet standardisée : il va dans un champ distinct, jamais dans `effect_size`.

---

# Partie IV — Synthèse

## 14. Les trois questions de la page Results

La page Results répond à **trois questions différentes**, et il faut les trois :

```
   « Est-ce du bruit ? »              →  p-value  +  décision
   « De combien, en unités métier ? » →  estimé B−A  +  intervalle de confiance
   « De combien, en unités de
      variabilité ? »                 →  taille d'effet
```

Aucune ne remplace les autres. C'est exactement l'ensemble de champs listé dans le contrat commun — et chacun a maintenant sa justification.

---

## 15. Arbre de décision du module d'interprétation

En positionnant l'IC par rapport à **0** et à **δ** (le seuil de pertinence pratique, fixé par l'analyste et non par la statistique), on obtient directement la spécification de `interpretation.py` :

```
                    0        δ
                    ┆        ┆
  (a)               ┆        ┆  ├────●────┤     significatif ET pertinent
  (b)               ┆ ├──●───┤  ┆              significatif mais négligeable
  (c)         ├─────●──────┤    ┆              non concluant, mais gros effet exclu
  (d)   ├─────┼───────●──────────────────┤     non concluant, étude trop imprécise
  (e) ├──●──┤ ┆        ┆                       effet NÉGATIF : B est pire
```

| Cas | Position de l'IC | Conclusion | Recommandation |
|---|---|---|---|
| (a) | entièrement au-delà de δ | Effet significatif et pertinent | Déployer B |
| (b) | exclut 0, mais reste sous δ | Significatif, mais trop petit pour compter | Ne pas déployer : le gain ne rembourse pas le coût |
| (c) | contient 0, entièrement dans ±δ | Non concluant, **mais un effet important est exclu** | Arrêter : B n'apporte rien d'utile |
| (d) | contient 0 et dépasse δ | Non concluant, étude trop imprécise | Relancer avec plus de données |
| (e) | entièrement en dessous de 0 | Effet négatif significatif | Ne pas déployer : B dégrade la métrique |

**Point crucial :** les cas (c) et (d) sont tous deux « non significatifs » mais appellent des recommandations **opposées**. C'est ce que la p-value seule ne permet jamais de distinguer, et c'est la justification concrète de l'exigence d'IC dans le contrat.

---

## 16. Ordre d'implémentation recommandé

### Ordre général (issu du PDF, confirmé)

1. Construire le package de statistiques en premier, avec un test binaire et un test continu.
2. Définir **un** modèle `StatisticalResult` stable et faire en sorte que toutes les méthodes le retournent.
3. Ajouter les diagnostics et les warnings structurés **avant** de construire une UI sophistiquée.
4. Créer les schémas et routes FastAPI, et les tester indépendamment.
5. Construire le workflow React autour de l'API : Dataset → Diagnostics → Method → Results → Export.
6. Ajouter la simulation avec des graines aléatoires explicites.
7. Ajouter les tests de validation statistique contre SciPy/Statsmodels et des vérifications Monte-Carlo.
8. Conteneuriser avec Docker Compose **seulement** une fois le workflow local fonctionnel de bout en bout.

### Ordre d'ajout des méthodes

```
1.  two_proportion_z    ← le plus simple, l'IC vient directement
2.  welch_t             ← le bon défaut continu
3.  fisher_exact        ← complète la famille binaire, valide le moteur de warnings
4.  mann_whitney_u      ← force à traiter le cas « estimate non standard »
5.  permutation         ← introduit la reproductibilité par graine
6.  bootstrap           ← réutilise la mécanique de graine, produit l'IC
7.  student_t           ← trivial une fois Welch fait
```

Cet ordre n'est pas arbitraire : **chaque étape stresse le contrat `StatisticalResult` sur un point différent.** S'il survit à Fisher (IC problématique) et à Mann-Whitney (estimé non standard), il survivra à tout. C'est la raison de ne pas construire les 7 méthodes d'un coup.

---

## 17. Points ouverts et prochaines étapes

### Ce qui rend le projet digne de confiance (principes retenus)

- Ne jamais choisir un test statistique en silence ; le choix est explicite.
- Garder le sens de l'effet fixe : **B − A**, toujours.
- Enregistrer les exclusions au lieu de corriger silencieusement des données invalides.
- Rendre les warnings **machine-readable**.
- Ne jamais interpréter un résultat non significatif comme une preuve que A et B sont égaux.
- Rapporter la significativité statistique **séparément** de l'importance pratique.
- Utiliser des graines fixes pour la permutation et le bootstrap.
- Tester l'implémentation contre des références statistiques indépendantes (SciPy, Statsmodels).

### Questions encore ouvertes

1. **IC de Fisher exact** : calculer l'IC de la différence de taux par une autre méthode documentée, ou laisser `null` avec warning ?
2. **Champs `null` du contrat** : formaliser, méthode par méthode, quels champs peuvent être absents et pourquoi.
3. **Test bilatéral / unilatéral** : exposé comme paramètre de la page Method — définir le défaut (bilatéral) et l'ergonomie de l'avertissement.
4. **Seuil δ de pertinence pratique** : saisi par l'analyste sur quelle page — Method ou Results ?
5. **Limite de taille du dataset** : fixer la valeur (proposition : 100 000 lignes) et le comportement au dépassement.

### Prochaine étape de travail

**Concevoir `StatisticalResult` champ par champ** : quels champs existent, quels types, lesquels peuvent être `null` et pour quelles méthodes. Ce contrat deviendra simultanément la spécification du package Python, des schémas Pydantic et des types TypeScript.

---

## Annexe — Glossaire

| Terme | Définition courte |
|---|---|
| **H₀ (hypothèse nulle)** | « Les deux variantes sont identiques ; tout écart observé est du bruit. » |
| **p-value** | Probabilité d'observer un écart au moins aussi extrême, *en supposant H₀ vraie*. |
| **α (alpha)** | Seuil de décision fixé avant l'expérience (souvent 0,05). |
| **Variabilité d'échantillonnage** | Le fait qu'un échantillon tiré au hasard produise un résultat différent à chaque tirage. |
| **Test A/A** | Expérience où les deux groupes reçoivent la même variante ; sert à mesurer le bruit. |
| **Estimé B−A** | Différence mesurée entre les groupes, dans le sens fixe B moins A. |
| **Estimation ponctuelle** | Un seul nombre estimant une vraie valeur inconnue. |
| **Intervalle de confiance** | Fourchette de valeurs plausibles pour le vrai effet ; le niveau (95 %) est une propriété de la méthode, pas de l'intervalle particulier. |
| **Taille d'effet** | Différence exprimée en unités de variabilité naturelle ; sans unité. |
| **δ (seuil de pertinence pratique)** | Effet minimum qui vaut économiquement la peine ; fixé par l'analyste, pas par la statistique. |
| **Hypothèses de validité (*assumptions*)** | Ce qu'un test suppose des données ; si elles sont violées, le résultat est faux même si le code est juste. |
| **Test bilatéral** | Compte les écarts extrêmes dans les deux sens ; à choisir avant de voir les données. |
| **Échangeabilité** | Sous H₀, une observation aurait pu appartenir indifféremment à l'un ou l'autre groupe. |
| **Lift relatif** | Variation exprimée en pourcentage de la valeur de départ ; n'est pas une taille d'effet standardisée. |

---

*Rapport généré à partir de la session de conception du 1er septembre 2026.*
