"""Services d'export : rapport PDF (ReportLab) et fichiers CSV."""

from __future__ import annotations

import csv
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas import AnalysisResponse, DataCsvExportRequest, PdfExportRequest


def generate_pdf_report(request: PdfExportRequest) -> bytes:
    """Génère un rapport PDF exhaustif et autonome pour une analyse A/B."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e293b"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
    )
    h2_style = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    bold_style = ParagraphStyle(
        "BodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )

    elements = []

    res = request.analysis.result
    interp = request.analysis.interpretation

    # 1. En-tête
    elements.append(Paragraph(f"Rapport d'Expérimentation A/B : {request.experiment_name}", title_style))
    elements.append(Paragraph(f"Auteur : {request.author} | Contrat : v{res.contract_version} | Méthode : {res.method}", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=15))

    # 2. Résumé exécutif
    elements.append(Paragraph("1. Résumé Exécutif", h2_style))
    status_color = "#16a34a" if res.decision == "reject_null" else "#64748b"
    decision_fr = "Effet statistiquement significatif" if res.decision == "reject_null" else "Non significatif (preuve insuffisante)"

    exec_summary_data = [
        [Paragraph("Décision statistique", bold_style), Paragraph(f"<font color='{status_color}'><b>{decision_fr}</b></font>", body_style)],
        [Paragraph("P-value", bold_style), Paragraph(f"{res.p_value:.4e} ({res.p_value_source})" if res.p_value is not None else "N/A", body_style)],
        [Paragraph("Estimation (B - A)", bold_style), Paragraph(f"{res.estimate['value']:.4f} {res.estimate.get('unit', '')}", body_style)],
        [Paragraph("Intervalle de Confiance", bold_style), Paragraph(f"[{res.confidence_interval.lower:.4f} ; {res.confidence_interval.upper:.4f}] ({int(res.confidence_interval.level * 100)}%, {res.confidence_interval.method})", body_style)],
        [Paragraph("Taille d'effet", bold_style), Paragraph(f"{res.effect_size.name} = {res.effect_size.value:.4f} ({res.effect_size.label or 'sans étiquette'}, {res.effect_size.convention or ''})", body_style)],
    ]
    if res.relative_lift is not None:
        exec_summary_data.append([Paragraph("Lift relatif", bold_style), Paragraph(f"{res.relative_lift * 100:+.2f} %", body_style)])

    exec_table = Table(exec_summary_data, colWidths=[160, 360])
    exec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(exec_table)
    elements.append(Spacer(1, 10))

    # 3. Interprétation et Recommandation
    if interp:
        elements.append(Paragraph("2. Interprétation et Recommandation Métier", h2_style))
        delta_str = f"δ = {interp.delta}" if interp.delta is not None else "Non spécifié"
        elements.append(Paragraph(f"<b>Arbre de décision : Cas ({interp.case.upper()})</b> — Seuil économique : {delta_str}", body_style))
        direction_str = "plus bas = mieux" if interp.favorable_direction == "lower_is_better" else "plus haut = mieux"
        elements.append(Paragraph(f"<b>Sens favorable de la métrique :</b> {direction_str}", body_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(f"<b>Significativité :</b> {interp.significance_statement}", body_style))
        elements.append(Paragraph(f"<b>Pertinence pratique :</b> {interp.practical_statement}", body_style))
        elements.append(Paragraph(f"<b>Recommandation :</b> <font color='#0284c7'><b>{interp.recommendation}</b></font>", body_style))
        elements.append(Spacer(1, 10))

    # 4. Groupes et Diagnostics
    elements.append(Paragraph("3. Effectifs et Données d'Échantillon", h2_style))
    grp_a = res.groups.get("a", {})
    grp_b = res.groups.get("b", {})
    group_data = [
        [Paragraph("Groupe", bold_style), Paragraph("Effectif (N)", bold_style), Paragraph("Taux / Moyenne", bold_style), Paragraph("Dispersion (SD)", bold_style)],
        [Paragraph("Groupe A (Contrôle)", body_style), Paragraph(str(grp_a.get("n", "")), body_style), Paragraph(str(grp_a.get("rate") or grp_a.get("mean") or "N/A"), body_style), Paragraph(str(grp_a.get("sd") or "—"), body_style)],
        [Paragraph("Groupe B (Traitement)", body_style), Paragraph(str(grp_b.get("n", "")), body_style), Paragraph(str(grp_b.get("rate") or grp_b.get("mean") or "N/A"), body_style), Paragraph(str(grp_b.get("sd") or "—"), body_style)],
    ]
    grp_table = Table(group_data, colWidths=[140, 100, 140, 140])
    grp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(grp_table)
    elements.append(Spacer(1, 10))

    # 5. Avertissements et Hypothèses
    if res.warnings:
        elements.append(Paragraph("4. Avertissements de Validité", h2_style))
        for w in res.warnings:
            elements.append(Paragraph(f"• <b>[{w.severity.upper()}] {w.code}</b>: {w.message}", body_style))
        elements.append(Spacer(1, 10))

    # 6. Reproductibilité
    elements.append(Paragraph("5. Métadonnées de Reproductibilité", h2_style))
    repro = res.reproducibility
    repro_data = [
        [Paragraph("Empreinte des données (SHA-256)", bold_style), Paragraph(repro.get("input_hash", ""), body_style)],
        [Paragraph("Calculé le (UTC)", bold_style), Paragraph(str(repro.get("computed_at", "")), body_style)],
        [Paragraph("Graine aléatoire (seed)", bold_style), Paragraph(str(repro.get("seed") or "Non applicable"), body_style)],
    ]
    repro_table = Table(repro_data, colWidths=[180, 340])
    repro_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(repro_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Export CSV
# ---------------------------------------------------------------------------

#: Colonnes du résumé CSV, dans l'ordre d'affichage. Une analyse = une ligne,
#: ce qui permet de concaténer plusieurs expériences dans un même tableur.
RESULT_CSV_COLUMNS = (
    "method", "metric_type", "alternative", "alpha",
    "n_a", "n_b", "rate_a", "rate_b", "mean_a", "mean_b", "sd_a", "sd_b",
    "statistic_name", "statistic_value", "df",
    "estimate_name", "estimate_b_minus_a", "unit",
    "ci_level", "ci_lower", "ci_upper", "ci_method",
    "p_value", "p_value_source", "decision",
    "effect_size_name", "effect_size_value", "effect_size_label", "relative_lift",
    "interpretation_case", "delta", "favorable_direction", "recommendation",
    "warnings", "seed", "n_resamples", "input_hash", "contract_version",
)


def _csv_bytes(rows: list[list[object]]) -> bytes:
    """Encode en UTF-8 avec BOM pour que les accents s'affichent dans Excel."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows([["" if v is None else v for v in row] for row in rows])
    return buffer.getvalue().encode("utf-8-sig")


def flatten_result(analysis: AnalysisResponse) -> dict[str, object]:
    """Aplatit un ``AnalysisResponse`` en un dictionnaire colonne -> valeur."""
    r = analysis.result
    a, b = r.groups.get("a", {}), r.groups.get("b", {})
    interp = analysis.interpretation
    return {
        "method": r.method,
        "metric_type": r.metric_type,
        "alternative": r.hypotheses.get("alternative"),
        "alpha": r.alpha,
        "n_a": a.get("n"),
        "n_b": b.get("n"),
        "rate_a": a.get("rate"),
        "rate_b": b.get("rate"),
        "mean_a": a.get("mean"),
        "mean_b": b.get("mean"),
        "sd_a": a.get("sd"),
        "sd_b": b.get("sd"),
        "statistic_name": r.statistic.get("name"),
        "statistic_value": r.statistic.get("value"),
        "df": r.statistic.get("df"),
        "estimate_name": r.estimate.get("name"),
        "estimate_b_minus_a": r.estimate.get("value"),
        "unit": r.estimate.get("unit"),
        "ci_level": r.confidence_interval.level,
        "ci_lower": r.confidence_interval.lower,
        "ci_upper": r.confidence_interval.upper,
        "ci_method": r.confidence_interval.method,
        "p_value": r.p_value,
        "p_value_source": r.p_value_source,
        "decision": r.decision,
        "effect_size_name": r.effect_size.name,
        "effect_size_value": r.effect_size.value,
        "effect_size_label": r.effect_size.label,
        "relative_lift": r.relative_lift,
        "interpretation_case": interp.case if interp else None,
        "delta": interp.delta if interp else None,
        "favorable_direction": interp.favorable_direction if interp else None,
        "recommendation": interp.recommendation if interp else None,
        "warnings": "|".join(w.code for w in r.warnings),
        "seed": r.reproducibility.get("seed"),
        "n_resamples": r.reproducibility.get("n_resamples"),
        "input_hash": r.reproducibility.get("input_hash"),
        "contract_version": r.contract_version,
    }


def generate_result_csv(analysis: AnalysisResponse) -> bytes:
    """CSV d'une ligne : en-tête + résultat aplati."""
    flat = flatten_result(analysis)
    return _csv_bytes([list(RESULT_CSV_COLUMNS), [flat[c] for c in RESULT_CSV_COLUMNS]])


def generate_data_csv(request: DataCsvExportRequest) -> bytes:
    """CSV long des observations analysées : une ligne par observation (groupe, valeur)."""
    rows: list[list[object]] = [["group", request.metric_name]]
    rows += [[request.label_a, v] for v in request.group_a]
    rows += [[request.label_b, v] for v in request.group_b]
    return _csv_bytes(rows)
