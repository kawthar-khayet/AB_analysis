"""Schémas Pydantic pour l'API REST FastAPI de l'A/B Analysis Workspace."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Schémas Dataset et Profilage
# ---------------------------------------------------------------------------

class CsvPreviewRequest(BaseModel):
    csv_text: str = Field(description="Contenu brut du fichier CSV")


class CsvPreviewResponse(BaseModel):
    columns: list[str]
    row_count: int
    preview_rows: list[dict[str, Any]]
    delimiter: str


class ValueCountSchema(BaseModel):
    value: str
    count: int


class ColumnProfileRequest(BaseModel):
    group_values: list[Any]
    metric_values: list[Any]
    group_column_name: str = "group"
    metric_column_name: str = "metric"


class GroupProfileResponse(BaseModel):
    n_rows: int
    n_missing: int
    n_distinct: int
    top_values: list[ValueCountSchema]


class MetricProfileResponse(BaseModel):
    n_rows: int
    n_missing: int
    n_distinct: int
    proposed_type: str
    proposed_unit: str | None
    decimal_separator: str
    top_values: list[ValueCountSchema]


class ColumnProfileResponse(BaseModel):
    group_profile: GroupProfileResponse
    metric_profile: MetricProfileResponse


class DatasetImportRequest(BaseModel):
    group_values: list[Any]
    metric_values: list[Any]
    group_a_value: str
    group_b_value: str
    metric_type: Literal["binary", "continuous"]
    binary_success_value: str | None = None
    binary_failure_value: str | None = None
    unit: str | None = None
    decimal_separator: Literal[".", ","] = "."
    group_column_name: str = "group"
    metric_column_name: str = "metric"
    exclude_unmapped_groups: bool = False


class ExclusionSummarySchema(BaseModel):
    reason: str
    count: int
    sample_row_indices: list[int]


class WarningSchema(BaseModel):
    code: str
    severity: str
    message: str
    affected_field: str | None = None
    suggested_alternative: str | None = None


class ValidationReportSchema(BaseModel):
    n_input: int
    n_retained: int
    n_excluded: int
    exclusion_rate: float
    exclusions: list[ExclusionSummarySchema]
    decimal_conversions: int
    warnings: list[WarningSchema]
    group_column_name: str
    metric_column_name: str


class DatasetImportResponse(BaseModel):
    group_a: list[float]
    group_b: list[float]
    metric_type: str
    unit: str
    report: ValidationReportSchema


# ---------------------------------------------------------------------------
# Schémas de Simulation
# ---------------------------------------------------------------------------

class SimulateBinaryRequest(BaseModel):
    rate_a: float = Field(..., ge=0.0, le=1.0)
    rate_b: float = Field(..., ge=0.0, le=1.0)
    n_a: int = Field(..., ge=2, le=500_000)
    n_b: int = Field(..., ge=2, le=500_000)
    seed: int | None = None


class SimulateContinuousRequest(BaseModel):
    mean_a: float
    mean_b: float
    sd_a: float = Field(..., gt=0.0)
    sd_b: float = Field(..., gt=0.0)
    n_a: int = Field(..., ge=2, le=500_000)
    n_b: int = Field(..., ge=2, le=500_000)
    distribution: Literal["normal", "lognormal", "exponential", "bimodal"] = "normal"
    unit: str = "sec"
    seed: int | None = None
    outlier_rate: float = Field(default=0.0, ge=0.0, le=0.5)
    missing_rate: float = Field(default=0.0, ge=0.0, le=0.5)


class SimulationResponse(BaseModel):
    group_column: list[str]
    metric_column: list[Any]
    group_a_value: str
    group_b_value: str
    metric_type: str
    unit: str
    seed: int


# ---------------------------------------------------------------------------
# Schémas Diagnostics & Compatibilité
# ---------------------------------------------------------------------------

class DiagnosticsRequest(BaseModel):
    group_a: list[float]
    group_b: list[float]
    metric_type: Literal["binary", "continuous"]
    unit: str = "unit"
    confidence_level: float = 0.95


class GroupDiagnosticsSchema(BaseModel):
    label: str
    n: int
    mean: float | None = None
    sd: float | None = None
    median: float | None = None
    rate: float | None = None
    successes: int | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    variance: float | None = None
    skewness: float | None = None
    outlier_count: int | None = None


class DiagnosticsResponse(BaseModel):
    metric_type: str
    unit: str
    group_a: GroupDiagnosticsSchema
    group_b: GroupDiagnosticsSchema
    balance: dict[str, Any]
    comparison: dict[str, Any]
    warnings: list[WarningSchema]


class MethodCompatibilitySchema(BaseModel):
    method: str
    compatible: bool
    reason: str | None = None
    assumptions: list[dict[str, Any]]
    warnings: list[WarningSchema]
    is_recommended: bool


class MethodsResponse(BaseModel):
    methods: list[MethodCompatibilitySchema]


# ---------------------------------------------------------------------------
# Schémas Analyse et Résultat
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    method: Literal[
        "two_proportion_z",
        "fisher_exact",
        "welch_t",
        "student_t",
        "mann_whitney_u",
        "permutation",
        "bootstrap",
    ]
    group_a: list[float]
    group_b: list[float]
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    alternative: Literal["two_sided", "greater", "less"] = "two_sided"
    confidence_level: float | None = None
    delta: float | None = None
    unit: str = "proportion"
    seed: int = 42
    n_resamples: int = 10_000


class ConfidenceIntervalSchema(BaseModel):
    level: float
    lower: float | None
    upper: float | None
    method: str | None


class EffectSizeSchema(BaseModel):
    name: str
    value: float
    convention: str | None = None
    label: str | None = None


class StatisticalResultSchema(BaseModel):
    method: str
    metric_type: str
    hypotheses: dict[str, Any]
    groups: dict[str, Any]
    statistic: dict[str, Any]
    alpha: float
    decision: str
    estimate: dict[str, Any]
    confidence_interval: ConfidenceIntervalSchema
    effect_size: EffectSizeSchema
    reproducibility: dict[str, Any]
    p_value: float | None
    p_value_source: str | None
    relative_lift: float | None
    n_excluded: int
    assumptions: list[dict[str, Any]]
    warnings: list[WarningSchema]
    contract_version: str


class InterpretationSchema(BaseModel):
    case: str
    significance_statement: str
    practical_statement: str
    recommendation: str
    delta: float | None = None
    caveats: list[str]


class AnalysisResponse(BaseModel):
    result: StatisticalResultSchema
    interpretation: InterpretationSchema | None = None


# ---------------------------------------------------------------------------
# Schémas Export PDF
# ---------------------------------------------------------------------------

class PdfExportRequest(BaseModel):
    analysis: AnalysisResponse
    experiment_name: str = "A/B Test Experiment"
    author: str = "Analyste"
