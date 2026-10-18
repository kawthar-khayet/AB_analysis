import React from "react";
import { WorkspaceLayout } from "./layout/WorkspaceLayout";
import { DatasetPage } from "./pages/Dataset";
import { DiagnosticsPage } from "./pages/Diagnostics";
import { ExportPage } from "./pages/Export";
import { MethodPage } from "./pages/Method";
import { ResultsPage } from "./pages/Results";
import { useWorkspace } from "./state/workspaceState";

export const App: React.FC = () => {
  const { currentStep } = useWorkspace();

  const renderCurrentStep = () => {
    switch (currentStep) {
      case "dataset":
        return <DatasetPage />;
      case "diagnostics":
        return <DiagnosticsPage />;
      case "method":
        return <MethodPage />;
      case "results":
        return <ResultsPage />;
      case "export":
        return <ExportPage />;
      default:
        return <DatasetPage />;
    }
  };

  return <WorkspaceLayout>{renderCurrentStep()}</WorkspaceLayout>;
};
