import React from "react";
import { AnalysisWarning } from "../types/dataset";

interface Props {
  warnings: AnalysisWarning[];
}

export const WarningList: React.FC<Props> = ({ warnings }) => {
  if (!warnings || warnings.length === 0) return null;

  const getBadgeStyle = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "critical":
        return { bg: "#fef2f2", text: "#b91c1c", border: "#fecaca" };
      case "warning":
        return { bg: "#fffbeb", text: "#b45309", border: "#fde68a" };
      default:
        return { bg: "#f0f9ff", text: "#0369a1", border: "#bae6fd" };
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px", margin: "14px 0" }}>
      {warnings.map((w, idx) => {
        const style = getBadgeStyle(w.severity);
        return (
          <div
            key={idx}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "10px",
              padding: "10px 14px",
              borderRadius: "8px",
              backgroundColor: style.bg,
              border: `1px solid ${style.border}`,
              fontSize: "0.85rem",
              lineHeight: 1.45,
            }}
          >
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 700,
                textTransform: "uppercase",
                padding: "2px 6px",
                borderRadius: "4px",
                backgroundColor: style.border,
                color: style.text,
                letterSpacing: "0.03em",
              }}
            >
              {w.code}
            </span>
            <div style={{ flex: 1, color: "#1e293b" }}>
              <span>{w.message}</span>
              {w.suggested_alternative && (
                <div style={{ marginTop: "4px", fontWeight: 600, color: style.text }}>
                  Alternative suggérée : {w.suggested_alternative}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
