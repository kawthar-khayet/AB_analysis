import { request } from "./client";
import {
  ColumnProfiles,
  DiagnosticsData,
  NormalizedDataset,
} from "../types/dataset";
import {
  AnalysisOutcome,
  MethodCompatibility,
} from "../types/results";

export interface PreviewResponse {
  columns: string[];
  row_count: number;
  preview_rows: Record<string, any>[];
  delimiter: string;
}

export const api = {
  // Santé
  health: () => request<{ status: string; version: string }>("/health"),

  // Datasets
  previewCsv: (csv_text: string) =>
    request<PreviewResponse>("/datasets/preview", {
      method: "POST",
      body: JSON.stringify({ csv_text }),
    }),

  profileColumns: (payload: {
    group_values: any[];
    metric_values: any[];
    group_column_name: string;
    metric_column_name: string;
  }) =>
    request<ColumnProfiles>("/datasets/profile", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  importDataset: (payload: any) =>
    request<NormalizedDataset>("/datasets/import", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getDiagnostics: (payload: {
    group_a: number[];
    group_b: number[];
    metric_type: string;
    unit: string;
    confidence_level?: number;
  }) =>
    request<DiagnosticsData>("/datasets/diagnostics", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Simulations
  simulateBinary: (payload: {
    rate_a: number;
    rate_b: number;
    n_a: number;
    n_b: number;
    seed?: number | null;
  }) =>
    request<{
      group_column: string[];
      metric_column: number[];
      group_a_value: string;
      group_b_value: string;
      metric_type: string;
      unit: string;
      seed: number;
    }>("/simulations/binary", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  simulateContinuous: (payload: {
    mean_a: number;
    mean_b: number;
    sd_a: number;
    sd_b: number;
    n_a: number;
    n_b: number;
    distribution?: string;
    unit?: string;
    seed?: number | null;
    outlier_rate?: number;
    missing_rate?: number;
  }) =>
    request<{
      group_column: string[];
      metric_column: (number | null)[];
      group_a_value: string;
      group_b_value: string;
      metric_type: string;
      unit: string;
      seed: number;
    }>("/simulations/continuous", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Méthodes et analyses
  getCompatibility: (payload: {
    group_a: number[];
    group_b: number[];
    metric_type: string;
    unit: string;
    confidence_level?: number;
  }) =>
    request<{ methods: MethodCompatibility[] }>("/methods/compatibility", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  runAnalysis: (payload: {
    method: string;
    group_a: number[];
    group_b: number[];
    alpha?: number;
    alternative?: string;
    confidence_level?: number;
    delta?: number | null;
    unit?: string;
    seed?: number;
    n_resamples?: number;
  }) =>
    request<AnalysisOutcome>("/analyses", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Exports
  exportPdf: async (payload: {
    analysis: AnalysisOutcome;
    experiment_name?: string;
    author?: string;
  }): Promise<Blob> => {
    return request<Blob>("/exports/pdf", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  exportJson: async (analysis: AnalysisOutcome): Promise<Blob> => {
    return request<Blob>("/exports/json", {
      method: "POST",
      body: JSON.stringify(analysis),
    });
  },
};
