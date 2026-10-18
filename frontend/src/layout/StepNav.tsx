import React from "react";
import { StepId, useWorkspace } from "../state/workspaceState";

interface StepConfig {
  id: StepId;
  label: string;
  sub: string;
}

const STEPS: StepConfig[] = [
  { id: "dataset", label: "Dataset", sub: "Import & Déclarations" },
  { id: "diagnostics", label: "Diagnostics", sub: "Qualité & Effectifs" },
  { id: "method", label: "Méthode", sub: "Choix de l'analyse" },
  { id: "results", label: "Résultats", sub: "Preuves & Interprétation" },
  { id: "export", label: "Export", sub: "Rapport PDF & Données" },
];

export const StepNav: React.FC = () => {
  const {
    currentStep,
    setCurrentStep,
    dataset,
    diagnostics,
    selectedMethod,
    analysisOutcome,
  } = useWorkspace();

  const getStatus = (id: StepId): "completed" | "active" | "todo" => {
    if (currentStep === id) return "active";
    if (id === "dataset" && dataset) return "completed";
    if (id === "diagnostics" && diagnostics) return "completed";
    if (id === "method" && selectedMethod && analysisOutcome) return "completed";
    if (id === "results" && analysisOutcome) return "completed";
    if (id === "export" && analysisOutcome) return "todo";
    return "todo";
  };

  const getIcon = (status: "completed" | "active" | "todo") => {
    if (status === "completed") return "✓";
    if (status === "active") return "●";
    return "○";
  };

  return (
    <nav style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
      {STEPS.map((step, idx) => {
        const status = getStatus(step.id);
        const isActive = currentStep === step.id;

        let iconColor = "#94a3b8";
        if (status === "completed") iconColor = "#16a34a";
        if (status === "active") iconColor = "#2563eb";

        return (
          <button
            key={step.id}
            onClick={() => setCurrentStep(step.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              padding: "10px 14px",
              borderRadius: "8px",
              border: "none",
              backgroundColor: isActive ? "#eff6ff" : "transparent",
              color: isActive ? "#1d4ed8" : "#334155",
              cursor: "pointer",
              textAlign: "left",
              width: "100%",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.backgroundColor = "#f1f5f9";
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.backgroundColor = "transparent";
            }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "24px",
                height: "24px",
                borderRadius: "50%",
                fontSize: "13px",
                fontWeight: 700,
                color: iconColor,
                backgroundColor: isActive ? "#dbeafe" : "#f8fafc",
                border: `1px solid ${isActive ? "#bfdbfe" : "#e2e8f0"}`,
              }}
            >
              {getIcon(status)}
            </span>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: "0.9rem", fontWeight: isActive ? 600 : 500 }}>
                {idx + 1}. {step.label}
              </span>
              <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                {step.sub}
              </span>
            </div>
          </button>
        );
      })}
    </nav>
  );
};
