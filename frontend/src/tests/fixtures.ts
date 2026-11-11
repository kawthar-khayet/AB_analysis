import { AnalysisOutcome, StatisticalResult } from "../types/results";

/** Résultat Welch réaliste (délai de paiement, en jours), proche de ce que renvoie l'API. */
export function makeResult(overrides: Partial<StatisticalResult> = {}): StatisticalResult {
  return {
    method: "welch_t",
    metric_type: "continuous",
    hypotheses: {
      alternative: "two_sided",
      null_text: "La moyenne du groupe B est égale à la moyenne du groupe A.",
      alternative_text: "Les moyennes des groupes A et B sont différentes.",
    },
    groups: {
      a: { n: 755, mean: 28.56, sd: 11.9, median: 26.6 },
      b: { n: 785, mean: 25.8, sd: 12.4, median: 23.8 },
    },
    statistic: { name: "t", value: -4.414, df: 1537.6 },
    alpha: 0.05,
    decision: "reject_null",
    estimate: { name: "difference_of_means", value: -2.7598, unit: "jours", direction: "B_minus_A" },
    confidence_interval: { level: 0.95, lower: -3.9861, upper: -1.5336, method: "welch_t_dist" },
    effect_size: { name: "cohens_d", value: -0.225, convention: "cohen_1988", label: "small" },
    reproducibility: {
      computed_at: "2026-11-10T21:00:00+00:00",
      input_hash: "sha256:abc123",
      library_versions: [["ab_stats", "0.1.0"]],
      seed: 42,
      n_resamples: null,
    },
    p_value: 0.0000108,
    p_value_source: "analytic",
    relative_lift: -0.0966,
    n_excluded: 860,
    assumptions: [
      { code: "INDEPENDENCE", description: "Observations indépendantes.", status: "unverifiable" },
    ],
    warnings: [],
    contract_version: "1.0",
    ...overrides,
  };
}

export function makeOutcome(overrides: Partial<StatisticalResult> = {}): AnalysisOutcome {
  return {
    result: makeResult(overrides),
    interpretation: {
      case: "e",
      significance_statement: "L'effet est statistiquement significatif.",
      practical_statement: "B réduit le délai de paiement.",
      recommendation: "Déployer B.",
      delta: 2,
      caveats: [],
    },
  };
}
