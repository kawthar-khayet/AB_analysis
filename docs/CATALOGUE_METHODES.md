# Catalogue des 4 méthodes statistiques

Ce catalogue présente les 4 méthodes d'analyse fréquentiste intégrées dans `ab_stats` : hypothèses, mesures d'effet et cas d'usage.
Il y a deux méthodes par type de métrique. Chaque paire associe une méthode « par défaut » à une alternative pour les cas où les hypothèses de la première sont fragiles.

---

## Synthèse

| Méthode | Famille de métrique | Paramétrique | Mesure d'effet | Méthode d'IC | Recommandation |
|---|---|---|---|---|---|
| `two_proportion_z` | Binaire | Oui | `cohens_h` | Normal approx unpooled | Défaut pour grands effectifs binaires ($\ge 10$ événements). |
| `fisher_exact` | Binaire | Non (Exact) | `cohens_h` | Newcombe hybrid score | Recommandé dès qu'un groupe compte $< 10$ événements. |
| `welch_t` | Continue | Oui | `cohens_d` / `hedges_g` | Welch t distribution | **Défaut recommandé** pour les métriques continues (robuste aux variances inégales). |
| `bootstrap` | Continue | Non (Rééchantillonnage) | `cohens_d` / `hedges_g` | Bootstrap percentile | Recommandé en cas de forte asymétrie ou de valeurs extrêmes : aucune hypothèse de normalité. |

La recommandation est une **suggestion affichée**, jamais un choix automatique : l'analyste sélectionne la méthode lui-même.

---

## 1. Méthodes binaires

### `two_proportion_z`
* **Question** : le taux de succès de B diffère-t-il de celui de A ?
* **Test** : $z = \dfrac{\hat p_B - \hat p_A}{\sqrt{\hat p(1-\hat p)(1/n_A + 1/n_B)}}$, avec $\hat p$ la proportion **poolée** (sous $H_0$, les deux groupes partagent un même taux).
* **IC** : intervalle de Wald **non poolé** sur la différence. On ne suppose plus $H_0$ pour estimer l'incertitude.
* **Taille d'effet** : $h = 2\arcsin(\sqrt{p_B}) - 2\arcsin(\sqrt{p_A})$.
* **Hypothèses** : observations indépendantes, effectifs suffisants pour l'approximation normale.
* **Avertissement** : `LOW_EVENT_COUNT` si $\min(x_A, n_A-x_A, x_B, n_B-x_B) < 10$, avec suggestion de `fisher_exact`.
* **Validation** : statistique et p-value identiques à `statsmodels.stats.proportion.proportions_ztest`.

### `fisher_exact`
* **Question** : le résultat (succès/échec) est-il indépendant du groupe ?
* **Test** : loi hypergéométrique exacte sur le tableau $2\times 2$. Il n'y a pas d'approximation normale, donc le test reste valide avec de petits effectifs.
* **IC** : Fisher ne fournit pas nativement d'IC sur la différence de taux. On emprunte une construction **déclarée** : Newcombe (score de Wilson combiné, sans correction de continuité).
* **Taille d'effet** : $h$ de Cohen. L'odds ratio est rapporté comme statistique.
* **Validation** : statistique et p-value identiques à `scipy.stats.fisher_exact`.

---

## 2. Méthodes continues

### `welch_t`
* **Question** : la moyenne de B diffère-t-elle de celle de A ?
* **Test** : $t = \dfrac{\bar x_B - \bar x_A}{\sqrt{s_A^2/n_A + s_B^2/n_B}}$. Chaque groupe garde sa propre variance.
* **Degrés de liberté** : approximation de Welch–Satterthwaite.
* **IC** : distribution $t$ avec les degrés de liberté de Welch.
* **Pourquoi Welch et pas Student ?** Student suppose des variances égales. Welch ne le suppose pas et ne perd presque rien quand elles le sont. C'est donc le défaut sûr, sans pré-test de variance.
* **Hypothèses** : indépendance, normalité approximative des **moyennes** (TCL dès $n \ge 30$).
* **Avertissements** : `SMALL_SAMPLE`, `HIGH_SKEWNESS` et `OUTLIERS_DETECTED` (ces deux derniers suggèrent `bootstrap`), ainsi que `UNBALANCED_GROUPS`.
* **Validation** : statistique et p-value identiques à `scipy.stats.ttest_ind(equal_var=False)`.

### `bootstrap`
* **Question** : quelle est l'incertitude sur la différence des moyennes, sans supposer de loi normale ?
* **Principe** : rééchantillonnage **avec remise** de chaque groupe, $N$ fois (10 000 par défaut). La différence des moyennes est recalculée à chaque tirage.
* **IC** : bornes empiriques percentiles $\alpha/2$ et $1 - \alpha/2$ de la distribution bootstrap.
* **P-value** : le bootstrap n'en a pas nativement. Elle est calculée sous $H_0$ en **recentrant** les deux échantillons sur la moyenne combinée, et déclarée par `p_value_source = bootstrap_shifted`.
* **Reproductibilité** : graine (`seed`) obligatoire. Même graine, même résultat.
* **Limites** : suppose des observations indépendantes. L'IC percentile peut perdre en couverture sur de très petits échantillons.
