# A/B Analysis Workspace

**A/B Analysis Workspace** est une application web d'analyse statistique fréquentiste dédiée à l'expérimentation A/B, inspirée par les principes de rigueur et de traçabilité d'[ExperimentOS](https://github.com/AhmedHABBANI/Experiment_OS).

L'application guide l'analyste de bout en bout :
1. **Dataset** : Import CSV (détection automatique des délimiteurs, exclusions tracées) ou simulations déterministes contrôlées.
2. **Diagnostics** : Contrôle de santé statistique (effectifs, asymétrie, détection d'outliers Tukey, ratios de variance, équilibre).
3. **Méthode** : Moteur de compatibilité guidant le choix parmi 7 méthodes sans automatisme silencieux.
4. **Résultats** : Contrat unifié `StatisticalResult` (p-value, estimation ponctuelle B − A, intervalle de confiance, taille d'effet standardisée avec sa convention, arbre d'interprétation économique).
5. **Export** : Rapport PDF autonome via ReportLab et archivage JSON/CSV.

---

## 🏛️ Les 7 Méthodes du Catalogue

| Méthode | Type de Métrique | Paramétrique | Estimé B − A | Mesure d'effet | Méthode d'IC |
|---|---|---|---|---|---|
| `two_proportion_z` | Binaire | Oui | Différence de proportions | $h$ de Cohen | Wald unpooled |
| `fisher_exact` | Binaire | Non (Exact) | Différence de proportions | $h$ de Cohen | Newcombe hybrid score |
| `welch_t` | Continue | Oui (Défaut recommandé) | Différence de moyennes | $d$ de Cohen / $g$ de Hedges | Welch t-distribution |
| `student_t` | Continue | Oui (Homoscédastique) | Différence de moyennes | $d$ de Cohen / $g$ de Hedges | Student t-distribution |
| `mann_whitney_u` | Continue / Ordinale | Non paramétrique | Décalage de Hodges-Lehmann | $\delta$ de Cliff | Hodges-Lehmann |
| `permutation` | Continue | Non paramétrique | Différence de moyennes | $d$ de Cohen / $g$ de Hedges | Bootstrap percentile |
| `bootstrap` | Continue | Non paramétrique | Différence de moyennes | $d$ de Cohen / $g$ de Hedges | Bootstrap percentile |

---

## 🔬 Arbre d'Interprétation Déterministe (§15)

L'interprétation confronte l'intervalle de confiance au seuil d'importance économique $\delta$ fixé par l'analyste :

* **(a)** : IC entièrement au-dessus de $\delta$ $\rightarrow$ **Significatif ET pertinent** (Déployer B).
* **(b)** : IC exclut 0 mais reste sous $\delta$ $\rightarrow$ **Significatif mais négligeable** (Ne pas déployer).
* **(c)** : IC contient 0 et est resserré dans $\pm\delta$ $\rightarrow$ **Non concluant, mais gros gain exclu** (Arrêter).
* **(d)** : IC contient 0 et dépasse $\delta$ $\rightarrow$ **Non concluant, étude trop imprécise** (Relancer).
* **(e)** : IC entièrement sous 0 $\rightarrow$ **Effet négatif significatif** (Rejeter B).

*Règle d'or : aucune phrase ne formule une égalité stricte entre variantes.*

---

## 🚀 Démarrage Rapide

### Prérequis
* Python 3.11+
* Node.js 18+ (avec npm)
* Docker & Docker Compose *(optionnel)*

### 1. Installation en local

#### Backend & Paquet Statistique
```bash
# Installation du package statistique
pip install -e ./packages

# Installation des dépendances backend
pip install -e ./backend

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

## 🧪 Tests & Validation Statistique

La suite de tests vérifie l'immuabilité, les calculs face aux références SciPy et Statsmodels, et inclut des simulations de Monte-Carlo (tests A/A sous $H_0$) :

```bash
# Tests du paquet statistique (264 tests)
pytest packages/ab_stats

# Tests d'intégration de l'API backend
PYTHONPATH="packages;backend" pytest backend/tests

# Build de vérification du frontend TypeScript
cd frontend && npm run build
```

---

## 📁 Structure du Projet

```
AB_analysis/
├── packages/ab_stats/          # Cœur scientifique pur (Python 3.11+, SciPy, Statsmodels)
│   ├── analyses/               # Les 7 méthodes fréquentistes
│   ├── tests/                  # Suite de tests exhaustifs
│   ├── compatibility.py        # Moteur de compatibilité & hypothèses
│   ├── confidence_intervals.py # Constructions d'IC (Wald, Newcombe, Welch, Hodges-Lehmann, Bootstrap)
│   ├── data.py                 # Profilage, validation & exclusions tracées
│   ├── diagnostics.py          # Statistiques descriptives & alertes
│   ├── effect_sizes.py         # Tailles d'effet standardisées (h, d, g, Cliff)
│   ├── interpretation.py       # Arbre de décision déterministe
│   ├── results.py              # Contrat StatisticalResult immuable
│   └── simulation.py           # Génération déterministe à graine fixe
├── backend/app/                # API REST FastAPI
│   ├── routes/                 # Endpoints typés (/datasets, /analyses, /exports, /health)
│   ├── schemas.py              # Modèles Pydantic miroirs
│   └── services/               # Orchestration & export PDF (ReportLab)
├── frontend/                   # Interface React 18 + TypeScript + Vite
│   ├── src/layout/             # WorkspaceLayout & StepNav à 5 étapes
│   ├── src/pages/              # Dataset, Diagnostics, Method, Results, Export
│   ├── src/components/         # ResultCard, ConfidenceIntervalPlot (SVG), WarningList
│   └── src/state/              # Persistance sessionStorage
├── docs/                       # Spécifications & conception détaillée
├── examples/                   # Fichiers CSV d'exemple (binaire & continu)
└── docker-compose.yml          # Déploiement multi-conteneurs
```
