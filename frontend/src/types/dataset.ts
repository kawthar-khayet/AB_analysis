export type MetricType = "binary" | "continuous";

export interface ValueCount {
  value: string;
  count: number;
}

export interface GroupProfile {
  n_rows: number;
  n_missing: number;
  n_distinct: number;
  top_values: ValueCount[];
}

export interface MetricProfile {
  n_rows: number;
  n_missing: number;
  n_distinct: number;
  proposed_type: MetricType | "unsupported";
  proposed_unit: string | null;
  decimal_separator: "." | ",";
  top_values: ValueCount[];
}

export interface ColumnProfiles {
  group_profile: GroupProfile;
  metric_profile: MetricProfile;
}

export interface ExclusionSummary {
  reason: string;
  count: number;
  sample_row_indices: number[];
}

export interface AnalysisWarning {
  code: string;
  severity: "info" | "warning" | "critical";
  message: string;
  affected_field?: string | null;
  suggested_alternative?: string | null;
}

export interface ValidationReport {
  n_input: number;
  n_retained: number;
  n_excluded: number;
  exclusion_rate: number;
  exclusions: ExclusionSummary[];
  decimal_conversions: number;
  warnings: AnalysisWarning[];
  group_column_name: string;
  metric_column_name: string;
}

export interface NormalizedDataset {
  group_a: number[];
  group_b: number[];
  metric_type: MetricType;
  unit: string;
  report: ValidationReport;
}

export interface GroupDiagnostics {
  label: string;
  n: number;
  mean?: number | null;
  sd?: number | null;
  median?: number | null;
  rate?: number | null;
  successes?: number | null;
  ci_lower?: number | null;
  ci_upper?: number | null;
  variance?: number | null;
  skewness?: number | null;
  outlier_count?: number | null;
}

export interface DiagnosticsData {
  metric_type: MetricType;
  unit: string;
  group_a: GroupDiagnostics;
  group_b: GroupDiagnostics;
  balance: {
    n_a: number;
    n_b: number;
    ratio: number;
  };
  comparison: Record<string, number | null>;
  warnings: AnalysisWarning[];
}
