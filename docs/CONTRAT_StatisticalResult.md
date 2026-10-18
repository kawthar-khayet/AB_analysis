# Contrat `StatisticalResult`

Ce document formalise le contrat de données universel retourné par les 7 méthodes d'analyse d'A/B Analysis Workspace.

---

## 1. Principes architecturaux

1. **Immuabilité** : Les objets sont définis avec `frozen=True` et `slots=True`. Les collections sont des tuples, garantissant qu'aucune valeur ne peut être modifiée après coup.
2. **Orientation fixe B − A** : L'effet est toujours calculé dans le sens **B minus A**. Une valeur positive indique que la variante B dépasse la variante de contrôle A.
3. **Principe « Never silently »** : Tout intervalle de confiance déclare sa méthode (`CIMethod`), toute p-value déclare sa provenance (`PValueSource`), et toute étiquette qualitative de taille d'effet déclare sa convention.
4. **Auto-suffisance** : Le résultat embarque les effectifs réels, les hypothèses testées et les métadonnées de reproductibilité (`input_hash`, `computed_at`, `library_versions`, `seed`), permettant d'exporter un rapport PDF complet sans accès à la base de données.
5. **Découplage de l'interprétation** : L'interprétation métier dépend d'un seuil $\delta$ saisi par l'analyste. Elle est donc séparée dans un objet distinct `Interpretation`.

---

## 2. Structure détaillée

### Schéma global

```python
StatisticalResult:
  method: Method
  metric_type: MetricType
  hypotheses: Hypotheses
  groups: Groups (a, b)
  statistic: Statistic
  alpha: float
  decision: Decision
  estimate: Estimate
  confidence_interval: ConfidenceInterval
  effect_size: EffectSize
  reproducibility: Reproducibility
  p_value: float | None
  p_value_source: PValueSource | None
  relative_lift: float | None
  n_excluded: int
  assumptions: tuple[Assumption, ...]
  warnings: tuple[AnalysisWarning, ...]
  contract_version: str = "1.0"
```

### Sous-objets

* **`Hypotheses`** : `alternative` (`two_sided`, `greater`, `less`), `null_text`, `alternative_text`.
* **`GroupSummary`** : `n`, `successes`, `rate`, `mean`, `sd`, `median`.
* **`Statistic`** : `name` (`"z"`, `"t"`, `"U"`, `"mean_diff"`, `"odds_ratio"`), `value`, `df`.
* **`Estimate`** : `name` (`difference_of_proportions`, `difference_of_means`, `hodges_lehmann`), `value`, `unit`, `direction = "B_minus_A"`.
* **`ConfidenceInterval`** : `level`, `lower`, `upper`, `method`.
* **`EffectSize`** : `name` (`cohens_h`, `cohens_d`, `hedges_g`, `cliffs_delta`), `value`, `convention`, `label`.
* **`Assumption`** : `code`, `description`, `status` (`satisfied`, `violated`, `unverifiable`), `detail`.
* **`AnalysisWarning`** : `code`, `severity` (`info`, `warning`, `critical`), `message`, `suggested_alternative`.
* **`Reproducibility`** : `computed_at`, `input_hash`, `library_versions`, `seed`, `n_resamples`.
* **`Interpretation`** : `case` (`"a"`, `"b"`, `"c"`, `"d"`, `"e"`), `significance_statement`, `practical_statement`, `recommendation`, `delta`, `caveats`.
