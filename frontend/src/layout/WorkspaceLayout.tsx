import React from "react";
import { StepNav } from "./StepNav";
import { useWorkspace } from "../state/workspaceState";

interface Props {
  children: React.ReactNode;
}

export const WorkspaceLayout: React.FC<Props> = ({ children }) => {
  const { dataset, resetAll } = useWorkspace();

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        backgroundColor: "#f8fafc",
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Sidebar */}
      <aside
        style={{
          width: "280px",
          backgroundColor: "#ffffff",
          borderRight: "1px solid #e2e8f0",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "24px 16px",
          position: "sticky",
          top: 0,
          height: "100vh",
          boxSizing: "border-box",
        }}
      >
        <div>
          {/* Logo / Header */}
          <div style={{ marginBottom: "28px", paddingLeft: "8px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "24px" }}>⚖️</span>
              <h1
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  color: "#0f172a",
                  margin: 0,
                  letterSpacing: "-0.02em",
                }}
              >
                A/B Workspace
              </h1>
            </div>
            <p style={{ margin: "4px 0 0 0", fontSize: "0.78rem", color: "#64748b" }}>
              Analyses fréquentistes rigoureuses
            </p>
          </div>

          {/* Navigation */}
          <StepNav />
        </div>

        {/* Footer / Context & Reset */}
        <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: "16px" }}>
          {dataset && (
            <div
              style={{
                backgroundColor: "#f8fafc",
                borderRadius: "6px",
                padding: "10px",
                marginBottom: "12px",
                fontSize: "0.8rem",
                color: "#475569",
              }}
            >
              <div style={{ fontWeight: 600, color: "#1e293b", marginBottom: "4px" }}>
                Données actives :
              </div>
              <div>Métrique : {dataset.metric_type} ({dataset.unit})</div>
              <div>
                N total : {dataset.report.n_retained} (A: {dataset.group_a.length}, B: {dataset.group_b.length})
              </div>
            </div>
          )}

          <button
            onClick={resetAll}
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "6px",
              border: "1px solid #e2e8f0",
              backgroundColor: "#ffffff",
              color: "#64748b",
              fontSize: "0.82rem",
              fontWeight: 500,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#ef4444";
              e.currentTarget.style.borderColor = "#fca5a5";
              e.currentTarget.style.backgroundColor = "#fef2f2";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "#64748b";
              e.currentTarget.style.borderColor = "#e2e8f0";
              e.currentTarget.style.backgroundColor = "#ffffff";
            }}
          >
            Réinitialiser la session
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "36px 48px",
          maxWidth: "1100px",
          margin: "0 auto",
          boxSizing: "border-box",
        }}
      >
        {children}
      </main>
    </div>
  );
};
