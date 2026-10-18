# Catalogue des 7 Méthodes Statistiques

Ce catalogue détaille les 7 méthodes d'analyse fréquentiste intégrées dans `ab_stats`, leurs hypothèses, leurs mesures d'effet et leurs cas d'usage.

---

## Synthèse

| Méthode | Famille de métrique | Paramétrique | Mesure d'effet | Méthode d'IC | Recommandation |
|---|---|---|---|---|---|
| `two_proportion_z` | Binaire | Oui | `cohens_h` | Normal approx unpooled | Défaut pour grands effectifs binaires ($\ge 10$ événements). |
| `fisher_exact` | Binaire | Non (Exact) | `cohens_h` | Newcombe hybrid score | Recommandé dès qu'un groupe compte $< 10$ événements. |
| `welch_t` | Continue | Oui | `cohens_d` / `hedges_g` | Welch t distribution | **Défaut recommandé** pour les métriques continues (robuste aux variances inégales). |
| `student_t` | Continue | Oui | `cohens_d` / `hedges_g` | Student t distribution | Supposé homoscédastique ($\sigma_A^2 = \sigma_B^2$) ; alerte si ratio $> 2$. |
| `mann_whitney_u` | Continue / Ordinale | Non | `cliffs_delta` | Hodges-Lehmann | Recommandé en cas de forte asymétrie ou de valeurs extrêmes. |
| `permutation` | Continue | Non (Monte-Carlo) | `cohens_d` / `hedges_g` | Bootstrap percentile | Test sous hypothèse d'échangeabilité, sans hypothèse de normalité. |
| `bootstrap` | Continue | Non (Rééchantillonnage) | `cohens_d` / `hedges_g` | Bootstrap percentile | P-value shifted sous $H_0$, estimation directe de la distribution d'échantillonnage. |

---

## 1. Méthodes binaires

### `two_proportion_z`
* **Test** : Différence de proportions avec erreur standard poolée sous $H_0$.
* **IC** : Intervalle de Wald non poolé sur la différence.
* **Taille d'effet** : $h = 2\arcsin(\sqrt{p_B}) - 2\arcsin(\sqrt{p_A})$.
* **Avertissement** : `LOW_EVENT_COUNT` si $\min(x_A, n_A-x_A, x_B, n_B-x_B) < 10$.

### `fisher_exact`
* **Test** : Loi hypergéométrique exacte sur tableau $2\times 2$.
* **IC** : Intervalle de Newcombe (score de Wilson combiné sans correction de continuité).
* **Taille d'effet** : $h$ de Cohen.

---

## 2. Méthodes continues

### `welch_t`
* **Test** : Test t sans hypothèse d'égalité des variances.
* **Degrés de liberté** : Approximation de Welch-Satterthwaite.
* **IC** : Distribution $t$ de Student avec degrés de liberté de Welch.

### `student_t`
* **Test** : Test t classique avec variance combinée (pooled variance).
* **Avertissement** : Émet `UNEQUAL_VARIANCES` dès que $\max(s_A^2, s_B^2) / \min(s_A^2, s_B^2) > 2.0$.

### `mann_whitney_u`
* **Test** : Comparaison des rangs entre les deux groupes.
* **Estimé** : Décalage médian de Hodges-Lehmann.
* **Taille d'effet** : Delta de Cliff $\delta = P(B > A) - P(B < A)$.

### `permutation`
* **Test** : Permutations aléatoires des assignations de groupe sous $H_0$.
* **P-value** : Fraction des différences permutées au moins aussi extrêmes que l'observée.
* **Reproductibilité** : Graine déterministe (`seed`).

### `bootstrap`
* **Test** : Rééchantillonnage avec remise.
* **IC** : Bornes empiriques percentiles $\alpha/2$ et $1 - \alpha/2$.
* **P-value** : Calculée sous $H_0$ par centrage des échantillons sur la moyenne combinée.
