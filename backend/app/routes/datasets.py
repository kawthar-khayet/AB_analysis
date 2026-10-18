"""Routes de traitement des jeux de données, profilage, validation et simulation."""

from __future__ import annotations

import csv
import dataclasses
import io
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
import numpy as np

from ab_stats import (
    BinaryEncoding,
    DecimalSeparator,
    Diagnostics,
    GroupMapping,
    MetricDeclaration,
    MetricType,
    diagnose,
    normalize,
    profile_group_column,
    profile_metric_column,
    simulate_binary,
    simulate_continuous,
)
from ab_stats.exceptions import ABStatsError
from app.schemas import (
    ColumnProfileRequest,
    ColumnProfileResponse,
    CsvPreviewRequest,
    CsvPreviewResponse,
    DatasetImportRequest,
    DatasetImportResponse,
    DiagnosticsRequest,
    DiagnosticsResponse,
    ExclusionSummarySchema,
    GroupDiagnosticsSchema,
    GroupProfileResponse,
    MetricProfileResponse,
    SimulateBinaryRequest,
    SimulateContinuousRequest,
    SimulationResponse,
    ValidationReportSchema,
    ValueCountSchema,
    WarningSchema,
)

router = APIRouter()


def _detect_delimiter(sample_text: str) -> str:
    """Détecte automatiquement le délimiteur (, ; \t)."""
    first_lines = "\n".join(sample_text.strip().splitlines()[:5])
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(first_lines, delimiters=",;\t")
        return dialect.delimiter
    except Exception:
        # Repli par défaut : compte d'occurrences
        counts = {",": first_lines.count(","), ";": first_lines.count(";"), "\t": first_lines.count("\t")}
        return max(counts, key=counts.get) if max(counts.values()) > 0 else ","


@router.post("/datasets/preview", response_model=CsvPreviewResponse)
def preview_csv(request: CsvPreviewRequest) -> CsvPreviewResponse:
    """Analyse un texte CSV brut, détecte le délimiteur et renvoie un aperçu des colonnes."""
    text = request.csv_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Le contenu CSV est vide.")

    delimiter = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        headers = next(reader)
    except StopIteration:
        raise HTTPException(status_code=400, detail="Aucune ligne d'en-tête trouvée dans le CSV.")

    preview_rows: list[dict[str, Any]] = []
    row_count = 0
    for row in reader:
        row_count += 1
        if len(preview_rows) < 10:
            preview_rows.append({headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))})

    return CsvPreviewResponse(
        columns=headers,
        row_count=row_count,
        preview_rows=preview_rows,
        delimiter=delimiter,
    )


@router.post("/datasets/profile", response_model=ColumnProfileResponse)
def profile_columns(request: ColumnProfileRequest) -> ColumnProfileResponse:
    """Profilage statistique automatique des deux colonnes sélectionnées avant déclaration."""
    g_prof = profile_group_column(request.group_values, name=request.group_column_name)
    m_prof = profile_metric_column(request.metric_values, name=request.metric_column_name)

    return ColumnProfileResponse(
        group_profile=GroupProfileResponse(
            n_rows=g_prof.n_rows,
            n_missing=g_prof.n_missing,
            n_distinct=g_prof.n_distinct,
            top_values=[ValueCountSchema(value=v.value, count=v.count) for v in g_prof.values[:10]],
        ),
        metric_profile=MetricProfileResponse(
            n_rows=m_prof.n_rows,
            n_missing=m_prof.n_missing,
            n_distinct=m_prof.n_distinct,
            proposed_type=m_prof.proposed_type.value,
            proposed_unit=m_prof.proposed_unit,
            decimal_separator=m_prof.decimal_separator.value,
            top_values=[ValueCountSchema(value=v.value, count=v.count) for v in m_prof.values[:10]],
        ),
    )


@router.post("/datasets/import", response_model=DatasetImportResponse)
def import_and_validate(request: DatasetImportRequest) -> DatasetImportResponse:
    """Valide les colonnes brutes contre la déclaration de l'analyste et produit les données normalisées."""
    m_type = MetricType(request.metric_type)
    mapping = GroupMapping(a=request.group_a_value, b=request.group_b_value)

    binary_encoding = None
    if m_type is MetricType.BINARY:
        succ = request.binary_success_value or "1"
        fail = request.binary_failure_value or "0"
        binary_encoding = BinaryEncoding(failure=fail, success=succ)

    declaration = MetricDeclaration(
        metric_type=m_type,
        unit=request.unit if m_type is MetricType.CONTINUOUS else None,
        binary_encoding=binary_encoding,
        decimal_separator=DecimalSeparator(request.decimal_separator),
    )

    try:
        dataset = normalize(
            request.group_values,
            request.metric_values,
            mapping=mapping,
            declaration=declaration,
            exclude_unmapped_groups=request.exclude_unmapped_groups,
            group_column_name=request.group_column_name,
            metric_column_name=request.metric_column_name,
        )
    except ABStatsError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict())

    rep = dataset.report
    return DatasetImportResponse(
        group_a=dataset.group_a.tolist(),
        group_b=dataset.group_b.tolist(),
        metric_type=dataset.metric_type.value,
        unit=dataset.unit,
        report=ValidationReportSchema(
            n_input=rep.n_input,
            n_retained=rep.n_retained,
            n_excluded=rep.n_excluded,
            exclusion_rate=rep.exclusion_rate,
            exclusions=[
                ExclusionSummarySchema(
                    reason=e.reason.value,
                    count=e.count,
                    sample_row_indices=list(e.sample_row_indices),
                )
                for e in rep.exclusions
            ],
            decimal_conversions=rep.decimal_conversions,
            warnings=[
                WarningSchema(
                    code=w.code,
                    severity=w.severity.value,
                    message=w.message,
                    affected_field=w.affected_field,
                    suggested_alternative=w.suggested_alternative.value if w.suggested_alternative else None,
                )
                for w in rep.warnings
            ],
            group_column_name=rep.group_column_name,
            metric_column_name=rep.metric_column_name,
        ),
    )


@router.post("/datasets/diagnostics", response_model=DiagnosticsResponse)
def compute_diagnostics(request: DiagnosticsRequest) -> DiagnosticsResponse:
    """Calcule les effectifs, statistiques descriptives et constats de qualité statistique."""
    m_type = MetricType(request.metric_type)
    arr_a = np.asarray(request.group_a, dtype=float)
    arr_b = np.asarray(request.group_b, dtype=float)

    # Création d'un dataset factice normalisé pour les diagnostics
    from ab_stats.data import NormalizedDataset, ValidationReport, GroupMapping, MetricDeclaration
    dummy_report = ValidationReport(
        n_input=arr_a.size + arr_b.size,
        n_retained=arr_a.size + arr_b.size,
        exclusions=(),
        group_mapping=GroupMapping("A", "B"),
        metric_declaration=MetricDeclaration(m_type, unit=request.unit if m_type is MetricType.CONTINUOUS else None),
        decimal_conversions=0,
        warnings=(),
        group_column_name="group",
        metric_column_name="metric",
    )
    dataset = NormalizedDataset(arr_a, arr_b, m_type, request.unit, dummy_report)

    try:
        diag = diagnose(dataset, confidence_level=request.confidence_level)
    except ABStatsError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict())

    def format_grp(g: Any) -> GroupDiagnosticsSchema:
        return GroupDiagnosticsSchema(
            label=g.label,
            n=g.n,
            mean=getattr(g, "mean", None),
            sd=getattr(g, "sd", None),
            median=getattr(g, "median", None),
            rate=getattr(g, "rate", None),
            successes=getattr(g, "successes", None),
            ci_lower=g.ci.lower if hasattr(g, "ci") and g.ci else None,
            ci_upper=g.ci.upper if hasattr(g, "ci") and g.ci else None,
            variance=getattr(g, "variance", None),
            skewness=getattr(g, "skewness", None),
            outlier_count=getattr(g, "n_outliers", None),
        )

    return DiagnosticsResponse(
        metric_type=diag.metric_type.value,
        unit=diag.unit,
        group_a=format_grp(diag.group_a),
        group_b=format_grp(diag.group_b),
        balance={
            "n_a": diag.balance.n_a,
            "n_b": diag.balance.n_b,
            "ratio": diag.balance.ratio,
        },
        comparison={
            f.name: getattr(diag.comparison, f.name)
            for f in dataclasses.fields(diag.comparison)
        },
        warnings=[
            WarningSchema(
                code=w.code,
                severity=w.severity.value,
                message=w.message,
                affected_field=w.affected_field,
                suggested_alternative=w.suggested_alternative.value if w.suggested_alternative else None,
            )
            for w in diag.warnings
        ],
    )


@router.post("/simulations/binary", response_model=SimulationResponse)
def generate_binary_simulation(request: SimulateBinaryRequest) -> SimulationResponse:
    """Génère déterministement un jeu de données binaire A/B."""
    sim = simulate_binary(
        n_a=request.n_a,
        n_b=request.n_b,
        p_a=request.rate_a,
        p_b=request.rate_b,
        seed=request.seed,
    )
    return SimulationResponse(
        group_column=list(sim.group),
        metric_column=sim.metric.tolist(),
        group_a_value="A",
        group_b_value="B",
        metric_type=sim.metric_type.value,
        unit="proportion",
        seed=sim.seed,
    )


@router.post("/simulations/continuous", response_model=SimulationResponse)
def generate_continuous_simulation(request: SimulateContinuousRequest) -> SimulationResponse:
    """Génère déterministement un jeu de données continu A/B."""
    sim = simulate_continuous(
        n_a=request.n_a,
        n_b=request.n_b,
        mean_a=request.mean_a,
        mean_b=request.mean_b,
        std_a=request.sd_a,
        std_b=request.sd_b,
        distribution=request.distribution,
        unit=request.unit,
        seed=request.seed,
        outlier_rate=request.outlier_rate,
        missing_rate=request.missing_rate,
    )
    metric_col = [
        (float(x) if x is not None and not (isinstance(x, float) and np.isnan(x)) else None)
        for x in sim.metric
    ]
    return SimulationResponse(
        group_column=list(sim.group),
        metric_column=metric_col,
        group_a_value="A",
        group_b_value="B",
        metric_type=sim.metric_type.value,
        unit=request.unit,
        seed=sim.seed,
    )
