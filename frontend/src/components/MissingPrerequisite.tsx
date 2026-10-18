import React from "react";
import { StepId, useWorkspace } from "../state/workspaceState";

interface Props {
  title: string;
  description: string;
  requiredStep: StepId;
  requiredStepLabel: string;
}

export const MissingPrerequisite: React.FC<Props> = ({
  title,
  description,
  requiredStep,
  requiredStepLabel,
}) => {
  const { setCurrentStep } = useWorkspace();

  return (
    <div style={{
      maxWidth: "600px",
      margin: "40px auto",
      padding: "32px",
      borderRadius: "12px",
      backgroundColor: "#ffffff",
      border: "1px solid #e2e8f0",
      boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
      textAlign: "center"
    }}>
      <div style={{ fontSize: "40px", marginBottom: "16px" }}>⚠️</div>
      <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "#1e293b", marginBottom: "8px" }}>
        {title}
      </h2>
      <p style={{ color: "#64748b", fontSize: "0.95rem", lineHeight: 1.5, marginBottom: "24px" }}>
        {description}
      </p>
      <button
        onClick={() => setCurrentStep(requiredStep)}
        style={{
          backgroundColor: "#2563eb",
          color: "#ffffff",
          padding: "10px 20px",
          borderRadius: "8px",
          fontWeight: 500,
          border: "none",
          cursor: "pointer",
          fontSize: "0.95rem",
          transition: "background-color 0.15s ease",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#1d4ed8")}
        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#2563eb")}
      >
        Aller à l'étape : {requiredStepLabel} →
      </button>
    </div>
  );
};
