import { AnalysisWarning, MetricType } from "./dataset";

export type Method =
  | "two_proportion_z"
  | "fisher_exact"
  | "welch_t"
  | "student_t"
  | "mann_whitney_u"
  | "permutation"
  | "bootstrap";

export type Alternative = "two_sided" | "greater" | "less";
export type Decision = "reject_null" | "fail_to_reject_null" | "not_applicable";
export type InterpretationCase = "a" | "b" | "c" | "d" | "e";

export interface Assumption {
  code: string;
  description: string;
  status: "satisfied" | "violated" | "unverifiable";
  detail?: string | null;
}

export interface MethodCompatibility {
  method: Method;
  compatible: boolean;
  reason?: string | null;
  assumptions: Assumption[];
  warnings: AnalysisWarning[];
  is_recommended: boolean;
}

export interface ConfidenceInterval {
  level: number;
  lower: number | null;
  upper: number | null;
  method: string | null;
}

export interface EffectSize {
  name: string;
  value: number;
  convention?: string | null;
  label?: string | null;
}

export interface StatisticalResult {
  method: Method;
  metric_type: MetricType;
  hypotheses: {
    alternative: Alternative;
    null_text: string;
    alternative_text: string;
  };
  groups: {
    a: {
      n: number;
      successes?: number | null;
      rate?: number | null;
      mean?: number | null;
      sd?: number | null;
      median?: number | null;
    };
    b: {
      n: number;
      successes?: number | null;
      rate?: number | null;
      mean?: number | null;
      sd?: number | null;
      median?: number | null;
    };
  };
  statistic: {
    name?: string | null;
    value?: number | null;
    df?: number | null;
  };
  alpha: number;
  decision: Decision;
  estimate: {
    name: string;
    value: number;
    unit: string;
    direction: string;
  };
  confidence_interval: ConfidenceInterval;
  effect_size: EffectSize;
  reproducibility: {
    computed_at: string;
    input_hash: string;
    library_versions: [string, string][] | Record<string, string>;
    seed?: number | null;
    n_resamples?: number | null;
  };
  p_value?: number | null;
  p_value_source?: string | null;
  relative_lift?: number | null;
  n_excluded: number;
  assumptions: Assumption[];
  warnings: AnalysisWarning[];
  contract_version: string;
}

export interface Interpretation {
  case: InterpretationCase;
  significance_statement: string;
  practical_statement: string;
  recommendation: string;
  delta?: number | null;
  caveats: string[];
}

export interface AnalysisOutcome {
  result: StatisticalResult;
  interpretation?: Interpretation | null;
}
