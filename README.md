# A/B Analysis Workspace

**A/B Analysis Workspace** est une application web d'analyse statistique fréquentiste dédiée à l'expérimentation A/B. Elle s'inspire des principes de rigueur et de traçabilité d'[ExperimentOS](https://github.com/AhmedHABBANI/Experiment_OS), avec un catalogue volontairement resserré à **4 méthodes**, chacune justifiable de bout en bout.

L'application guide l'analyste de bout en bout :
1. **Dataset** : import CSV (détection automatique des délimiteurs, exclusions tracées) ou simulations déterministes contrôlées.
2. **Diagnostics** : contrôle de santé statistique (effectifs, asymétrie, outliers selon Tukey, ratio de variances, équilibre des groupes).
3. **Méthode** : un moteur de compatibilité guide le choix parmi 4 méthodes, sans automatisme silencieux.
4. **Résultats** : contrat unifié `StatisticalResult` (p-value, estimation ponctuelle B − A, intervalle de confiance, taille d'effet standardisée avec sa convention, arbre d'interprétation économique).
5. **Export** : rapport PDF autonome (ReportLab), JSON complet, résultat aplati en CSV et données analysées en CSV.

---

## 🏛️ Les 4 méthodes du catalogue

| Méthode | Type de métrique | Paramétrique | Estimé B − A | Mesure d'effet | Méthode d'IC |
|---|---|---|---|---|---|
| `two_proportion_z` | Binaire | Oui | Différence de proportions | $h$ de Cohen | Wald unpooled |
| `fisher_exact` | Binaire | Non (exact) | Différence de proportions | $h$ de Cohen | Newcombe hybrid score |
| `welch_t` | Continue | Oui (défaut recommandé) | Différence de moyennes | $d$ de Cohen / $g$ de Hedges | Welch t-distribution |
| `bootstrap` | Continue | Non paramétrique | Différence de moyennes | $d$ de Cohen / $g$ de Hedges | Bootstrap percentile |

Deux méthodes par type de métrique : une méthode par défaut et une alternative quand ses hypothèses sont fragiles (petits effectifs pour le z-test, forte asymétrie pour Welch). Détails dans [docs/CATALOGUE_METHODES.md](docs/CATALOGUE_METHODES.md).

---

## 🔬 Arbre d'interprétation déterministe (§15)

L'interprétation confronte l'intervalle de confiance au seuil d'importance économique $\delta$ fixé par l'analyste :

* **(a)** : IC entièrement au-dessus de $\delta$ $\rightarrow$ **Significatif ET pertinent** (déployer B).
* **(b)** : IC exclut 0 mais reste sous $\delta$ $\rightarrow$ **Significatif mais négligeable** (ne pas déployer).
* **(c)** : IC contient 0 et reste dans $\pm\delta$ $\rightarrow$ **Non concluant, mais gros gain exclu** (arrêter).
* **(d)** : IC contient 0 et dépasse $\delta$ $\rightarrow$ **Non concluant, étude trop imprécise** (relancer).
* **(e)** : IC entièrement sous 0 $\rightarrow$ **Effet négatif significatif** (rejeter B).

*Règle d'or : aucune phrase n'affirme une égalité stricte entre variantes.*

---

## 📊 Jeu de données d'exemple

[`data/relances_paiement/`](data/relances_paiement/description.md) contient 2 400 factures impayées simulées (graine fixe), réparties au hasard entre une relance par e-mail (`control`) et une relance e-mail + appel (`treatment`). Le fichier se prête à deux analyses :

* `recovered` (binaire) → `two_proportion_z` / `fisher_exact` : **non concluant** (+2,5 pts, IC contenant 0), alors que la simulation contient un vrai écart de +5 pts. C'est un cas d'école de puissance insuffisante.
* `days_to_payment` (continue) → `welch_t` / `bootstrap` : **−2,8 jours**, significatif. Les 860 valeurs vides (factures non recouvrées) sont exclues et tracées.

Des fichiers plus petits se trouvent dans [`examples/`](examples/).

---

## 🚀 Démarrage rapide

### Prérequis
* Python 3.11+
* Node.js 18+ (avec npm)
* Docker & Docker Compose *(optionnel)*

### 1. Installation en local

#### Backend & paquet statistique
```bash
# Installation du package statistique
pip install -e ./packages

# Installation des dépendances backend
pip install -e "./backend[dev]"

# Lancer le serveur backend FastAPI
uvicorn app.main:app --app-dir ./backend --reload --port 8000
```
L'API est accessible sur `http://localhost:8000` et la documentation interactive sur `http://localhost:8000/docs`.

#### Frontend React
```bash
cd frontend
npm install
npm run dev
```
L'interface est accessible sur `http://localhost:3000`.

### 2. Démarrage via Docker Compose

```bash
docker compose up --build
```
* Frontend : `http://localhost:3000`
* Backend : `http://localhost:8000`

---

## 🧪 Tests & validation statistique

Les tests vérifient l'immuabilité du contrat et comparent les calculs aux références SciPy et Statsmodels. Ils incluent des simulations de Monte-Carlo (tests A/A sous $H_0$) :

```bash
# Paquet statistique (257 tests)
pytest packages/ab_stats

# API FastAPI, workflow complet sur le jeu d'exemple (20 tests)
PYTHONPATH="packages;backend" pytest backend/tests     # Windows
PYTHONPATH="packages:backend" pytest backend/tests     # Linux / macOS

# Frontend : tests Vitest (18 tests) puis vérification TypeScript + build
cd frontend && npm test && npm run build
```

### Intégration continue

Trois workflows GitHub Actions ([`.github/workflows/`](.github/workflows/)) :

| Workflow | Vérifie |
|---|---|
| `backend.yml` | Lint `ruff`, tests du paquet et de l'API sous Python 3.11 et 3.12, reproductibilité octet par octet du jeu d'exemple |
| `frontend.yml` | Tests Vitest, vérification TypeScript et build de production |
| `docker.yml` | Build des images, démarrage de la stack, santé de l'API et service du frontend |

---

## 📁 Structure du projet

```
AB_analysis/
├── packages/ab_stats/          # Cœur scientifique pur (Python 3.11+, SciPy, Statsmodels)
│   ├── analyses/               # Les 4 méthodes : binary.py (z, Fisher), continuous.py (Welch), resampling.py (bootstrap)
│   ├── tests/                  # Tests unitaires, références SciPy/Statsmodels, Monte-Carlo
│   ├── compatibility.py        # Moteur de compatibilité & hypothèses
│   ├── confidence_intervals.py # Constructions d'IC (Wald, Newcombe, Welch, bootstrap percentile)
│   ├── data.py                 # Profilage, validation & exclusions tracées
│   ├── diagnostics.py          # Statistiques descriptives & alertes
│   ├── effect_sizes.py         # Tailles d'effet standardisées (h, d, g)
│   ├── interpretation.py       # Arbre de décision déterministe
│   ├── results.py              # Contrat StatisticalResult immuable
│   └── simulation.py           # Génération déterministe à graine fixe
├── backend/app/                # API REST FastAPI
│   ├── routes/                 # Endpoints typés (/datasets, /simulations, /analyses, /exports, /health)
│   ├── schemas.py              # Modèles Pydantic miroirs
│   └── services/               # Orchestration & exports (PDF ReportLab, CSV)
├── frontend/                   # Interface React 18 + TypeScript + Vite
│   ├── src/layout/             # WorkspaceLayout & StepNav à 5 étapes
│   ├── src/pages/              # Dataset, Diagnostics, Method, Results, Export
│   ├── src/components/         # ResultCard, ConfidenceIntervalPlot (SVG), WarningList
│   ├── src/state/              # Persistance sessionStorage
│   └── src/tests/              # Tests Vitest + Testing Library
├── data/relances_paiement/     # Jeu d'exemple réaliste + générateur + description
├── docs/                       # Spécifications & conception détaillée
├── examples/                   # Petits fichiers CSV d'exemple (binaire & continu)
├── .github/workflows/          # CI backend, frontend, Docker
└── docker-compose.yml          # Déploiement multi-conteneurs
```
