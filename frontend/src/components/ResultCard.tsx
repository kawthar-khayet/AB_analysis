import React from "react";
import { StatisticalResult } from "../types/results";
import { ConfidenceIntervalPlot } from "./ConfidenceIntervalPlot";
import { WarningList } from "./WarningList";

interface Props {
  result: StatisticalResult;
  delta?: number | null;
}

export const ResultCard: React.FC<Props> = ({ result, delta }) => {
  const isSig = result.decision === "reject_null";

  const formatPValue = (p?: number | null) => {
    if (p === undefined || p === null) return "Non calculée";
    if (p < 0.001) return "p < 0,001";
    return `p = ${p.toFixed(4)}`;
  };

  return (
    <div
      style={{
        backgroundColor: "#ffffff",
        borderRadius: "12px",
        border: "1px solid #e2e8f0",
        padding: "24px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
      }}
    >
      {/* En-tête du résultat */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          borderBottom: "1px solid #f1f5f9",
          paddingBottom: "16px",
          marginBottom: "16px",
        }}
      >
        <div>
          <span
            style={{
              fontSize: "0.75rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#64748b",
            }}
          >
            Méthode d'analyse : {result.method}
          </span>
          <h2 style={{ fontSize: "1.3rem", fontWeight: 700, color: "#0f172a", margin: "4px 0 0 0" }}>
            {result.hypotheses.alternative_text}
          </h2>
          <div style={{ fontSize: "0.85rem", color: "#64748b", marginTop: "2px" }}>
            H0 : {result.hypotheses.null_text}
          </div>
        </div>

        <div
          style={{
            padding: "8px 16px",
            borderRadius: "9999px",
            fontSize: "0.85rem",
            fontWeight: 700,
            backgroundColor: isSig ? "#dcfce7" : "#f1f5f9",
            color: isSig ? "#15803d" : "#475569",
            border: `1px solid ${isSig ? "#bbf7d0" : "#e2e8f0"}`,
          }}
        >
          {isSig ? "✓ REJET DE H0 (Significatif)" : "○ NON REJET DE H0 (Preuve insuffisante)"}
        </div>
      </div>

      {/* Métriques clés en grille */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "16px",
          marginBottom: "20px",
        }}
      >
        <div style={{ backgroundColor: "#f8fafc", padding: "14px", borderRadius: "8px" }}>
          <div style={{ fontSize: "0.75rem", color: "#64748b", fontWeight: 600 }}>P-VALUE</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", marginTop: "2px" }}>
            {formatPValue(result.p_value)}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
            Source : {result.p_value_source || "N/A"} (seuil α = {result.alpha})
          </div>
        </div>

        <div style={{ backgroundColor: "#f8fafc", padding: "14px", borderRadius: "8px" }}>
          <div style={{ fontSize: "0.75rem", color: "#64748b", fontWeight: 600 }}>ESTIMATION B − A</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", marginTop: "2px" }}>
            {result.estimate.value > 0 ? "+" : ""}
            {result.estimate.value.toFixed(4)} {result.estimate.unit}
          </div>
          {result.relative_lift !== null && result.relative_lift !== undefined && (
            <div style={{ fontSize: "0.75rem", color: result.relative_lift >= 0 ? "#16a34a" : "#dc2626", fontWeight: 600 }}>
              Lift : {result.relative_lift >= 0 ? "+" : ""}{(result.relative_lift * 100).toFixed(2)} %
            </div>
          )}
        </div>

        <div style={{ backgroundColor: "#f8fafc", padding: "14px", borderRadius: "8px" }}>
          <div style={{ fontSize: "0.75rem", color: "#64748b", fontWeight: 600 }}>TAILLE D'EFFET</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", marginTop: "2px" }}>
            {result.effect_size.value.toFixed(4)}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
            {result.effect_size.name} ({result.effect_size.label || "convention"} • {result.effect_size.convention || ""})
          </div>
        </div>

        {result.statistic.name && (
          <div style={{ backgroundColor: "#f8fafc", padding: "14px", borderRadius: "8px" }}>
            <div style={{ fontSize: "0.75rem", color: "#64748b", fontWeight: 600 }}>STATISTIQUE</div>
            <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", marginTop: "2px" }}>
              {result.statistic.name} = {result.statistic.value?.toFixed(3)}
            </div>
            {result.statistic.df !== null && result.statistic.df !== undefined && (
              <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
                Degrés de liberté : {result.statistic.df.toFixed(1)}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Tracé de l'intervalle de confiance */}
      <ConfidenceIntervalPlot
        confidenceInterval={result.confidence_interval}
        estimate={result.estimate.value}
        delta={delta}
        unit={result.estimate.unit}
      />

      {/* Avertissements */}
      <WarningList warnings={result.warnings} />

      {/* Hypothèses de validité */}
      <div style={{ marginTop: "20px", borderTop: "1px solid #f1f5f9", paddingTop: "14px" }}>
        <h4 style={{ fontSize: "0.9rem", fontWeight: 600, color: "#334155", marginBottom: "8px" }}>
          Hypothèses de validité statistique :
        </h4>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {result.assumptions.map((a, idx) => {
            const isOk = a.status === "satisfied";
            const isViolated = a.status === "violated";
            const color = isOk ? "#16a34a" : isViolated ? "#dc2626" : "#64748b";
            const icon = isOk ? "✓" : isViolated ? "✗" : "•";

            return (
              <div key={idx} style={{ fontSize: "0.82rem", color: "#475569", display: "flex", gap: "8px" }}>
                <span style={{ color, fontWeight: 700 }}>[{icon}]</span>
                <span>
                  <b>{a.code}</b> : {a.description} {a.detail && <span style={{ color: "#64748b" }}>({a.detail})</span>}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
