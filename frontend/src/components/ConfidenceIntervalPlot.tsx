import React from "react";
import { ConfidenceInterval } from "../types/results";

interface Props {
  confidenceInterval: ConfidenceInterval;
  estimate: number;
  delta?: number | null;
  unit: string;
}

export const ConfidenceIntervalPlot: React.FC<Props> = ({
  confidenceInterval,
  estimate,
  delta,
  unit,
}) => {
  if (
    confidenceInterval.lower === null ||
    confidenceInterval.upper === null ||
    !isFinite(confidenceInterval.lower) ||
    !isFinite(confidenceInterval.upper)
  ) {
    return (
      <div style={{ color: "#64748b", fontStyle: "italic", padding: "16px" }}>
        Intervalle de confiance non disponible pour cette méthode.
      </div>
    );
  }

  const lower = confidenceInterval.lower;
  const upper = confidenceInterval.upper;

  // Déterminer les bornes globales de l'échelle d'affichage
  const allValues = [lower, upper, estimate, 0];
  if (delta !== null && delta !== undefined) {
    allValues.push(delta);
    allValues.push(-delta);
  }

  const rawMin = Math.min(...allValues);
  const rawMax = Math.max(...allValues);
  const padding = (rawMax - rawMin) * 0.15 || 0.05;
  const xMin = rawMin - padding;
  const xMax = rawMax + padding;

  const width = 600;
  const height = 120;
  const margin = { left: 40, right: 40, top: 30, bottom: 40 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const scaleX = (val: number) => {
    return margin.left + ((val - xMin) / (xMax - xMin)) * innerWidth;
  };

  const yCenter = margin.top + innerHeight / 2;
  const xLower = scaleX(lower);
  const xUpper = scaleX(upper);
  const xEst = scaleX(estimate);
  const xZero = scaleX(0);
  const xDelta = delta !== null && delta !== undefined ? scaleX(delta) : null;

  const excludesZero = lower > 0 || upper < 0;
  const ciColor = excludesZero ? (lower > 0 ? "#16a34a" : "#dc2626") : "#0284c7";

  return (
    <div
      style={{
        backgroundColor: "#ffffff",
        borderRadius: "10px",
        border: "1px solid #e2e8f0",
        padding: "16px 20px",
        margin: "16px 0",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "8px",
        }}
      >
        <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
          Visualisation de l'effet estimé et de l'IC {intToStr(confidenceInterval.level * 100)}%
        </span>
        <span style={{ fontSize: "0.8rem", color: "#64748b" }}>
          Unité : <b>{unit}</b> ({confidenceInterval.method})
        </span>
      </div>

      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
        {/* Ligne d'axe horizontal */}
        <line
          x1={margin.left}
          y1={yCenter}
          x2={width - margin.right}
          y2={yCenter}
          stroke="#cbd5e1"
          strokeWidth="1.5"
        />

        {/* Ligne de référence H0 : 0 */}
        <line
          x1={xZero}
          y1={margin.top - 10}
          x2={xZero}
          y2={yCenter + 25}
          stroke="#94a3b8"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />
        <text
          x={xZero}
          y={margin.top - 14}
          textAnchor="middle"
          fontSize="11"
          fill="#64748b"
          fontWeight="600"
        >
          H0 (0)
        </text>

        {/* Ligne de référence Seuil économique delta */}
        {xDelta !== null && (
          <>
            <line
              x1={xDelta}
              y1={margin.top - 10}
              x2={xDelta}
              y2={yCenter + 25}
              stroke="#f59e0b"
              strokeWidth="1.5"
              strokeDasharray="3 3"
            />
            <text
              x={xDelta}
              y={margin.top - 14}
              textAnchor="middle"
              fontSize="11"
              fill="#d97706"
              fontWeight="600"
            >
              δ ({delta})
            </text>
          </>
        )}

        {/* Intervalle de confiance (barre) */}
        <line
          x1={xLower}
          y1={yCenter}
          x2={xUpper}
          y2={yCenter}
          stroke={ciColor}
          strokeWidth="4"
          strokeLinecap="round"
        />

        {/* Bornes verticales [ et ] */}
        <line
          x1={xLower}
          y1={yCenter - 8}
          x2={xLower}
          y2={yCenter + 8}
          stroke={ciColor}
          strokeWidth="2.5"
        />
        <line
          x1={xUpper}
          y1={yCenter - 8}
          x2={xUpper}
          y2={yCenter + 8}
          stroke={ciColor}
          strokeWidth="2.5"
        />

        {/* Point de l'estimation ponctuelle */}
        <circle cx={xEst} cy={yCenter} r="5" fill="#0f172a" stroke="#ffffff" strokeWidth="2" />

        {/* Textes des bornes */}
        <text
          x={xLower}
          y={yCenter + 22}
          textAnchor="middle"
          fontSize="10"
          fill="#334155"
          fontFamily="monospace"
        >
          {formatNum(lower)}
        </text>
        <text
          x={xUpper}
          y={yCenter + 22}
          textAnchor="middle"
          fontSize="10"
          fill="#334155"
          fontFamily="monospace"
        >
          {formatNum(upper)}
        </text>
        <text
          x={xEst}
          y={yCenter - 10}
          textAnchor="middle"
          fontSize="11"
          fontWeight="700"
          fill="#0f172a"
          fontFamily="monospace"
        >
          {formatNum(estimate)}
        </text>
      </svg>
    </div>
  );
};

function formatNum(n: number): string {
  if (Math.abs(n) < 0.001 && n !== 0) return n.toExponential(2);
  return n.toFixed(4);
}

function intToStr(n: number): string {
  return Math.round(n).toString();
}
