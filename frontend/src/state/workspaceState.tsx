import React, { createContext, useContext, useEffect, useState } from "react";
import { DiagnosticsData, NormalizedDataset } from "../types/dataset";
import { Alternative, AnalysisOutcome, Method } from "../types/results";

export type StepId = "dataset" | "diagnostics" | "method" | "results" | "export";

export interface WorkspaceState {
  currentStep: StepId;
  setCurrentStep: (step: StepId) => void;

  dataset: NormalizedDataset | null;
  setDataset: (data: NormalizedDataset | null) => void;

  diagnostics: DiagnosticsData | null;
  setDiagnostics: (diag: DiagnosticsData | null) => void;

  selectedMethod: Method | null;
  setSelectedMethod: (method: Method | null) => void;

  alpha: number;
  setAlpha: (alpha: number) => void;

  alternative: Alternative;
  setAlternative: (alt: Alternative) => void;

  delta: number | null;
  setDelta: (delta: number | null) => void;

  seed: number;
  setSeed: (seed: number) => void;

  analysisOutcome: AnalysisOutcome | null;
  setAnalysisOutcome: (outcome: AnalysisOutcome | null) => void;

  resetAll: () => void;
}

const STORAGE_KEY = "ab_analysis_workspace_state_v1";

const WorkspaceContext = createContext<WorkspaceState | null>(null);

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [currentStep, setCurrentStep] = useState<StepId>("dataset");
  const [dataset, setDataset] = useState<NormalizedDataset | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsData | null>(null);
  const [selectedMethod, setSelectedMethod] = useState<Method | null>(null);
  const [alpha, setAlpha] = useState<number>(0.05);
  const [alternative, setAlternative] = useState<Alternative>("two_sided");
  const [delta, setDelta] = useState<number | null>(null);
  const [seed, setSeed] = useState<number>(42);
  const [analysisOutcome, setAnalysisOutcome] = useState<AnalysisOutcome | null>(null);

  // Charger depuis sessionStorage au montage
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.currentStep) setCurrentStep(parsed.currentStep);
        if (parsed.dataset) setDataset(parsed.dataset);
        if (parsed.diagnostics) setDiagnostics(parsed.diagnostics);
        if (parsed.selectedMethod) setSelectedMethod(parsed.selectedMethod);
        if (parsed.alpha !== undefined) setAlpha(parsed.alpha);
        if (parsed.alternative) setAlternative(parsed.alternative);
        if (parsed.delta !== undefined) setDelta(parsed.delta);
        if (parsed.seed !== undefined) setSeed(parsed.seed);
        if (parsed.analysisOutcome) setAnalysisOutcome(parsed.analysisOutcome);
      }
    } catch (e) {
      console.warn("Échec de restauration de session:", e);
    }
  }, []);

  // Sauvegarder dans sessionStorage à chaque mise à jour
  useEffect(() => {
    try {
      const stateToSave = {
        currentStep,
        dataset,
        diagnostics,
        selectedMethod,
        alpha,
        alternative,
        delta,
        seed,
        analysisOutcome,
      };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stateToSave));
    } catch (e) {
      console.warn("Échec de sauvegarde de session:", e);
    }
  }, [
    currentStep,
    dataset,
    diagnostics,
    selectedMethod,
    alpha,
    alternative,
    delta,
    seed,
    analysisOutcome,
  ]);

  const resetAll = () => {
    sessionStorage.removeItem(STORAGE_KEY);
    setDataset(null);
    setDiagnostics(null);
    setSelectedMethod(null);
    setDelta(null);
    setAnalysisOutcome(null);
    setCurrentStep("dataset");
  };

  return (
    <WorkspaceContext.Provider
      value={{
        currentStep,
        setCurrentStep,
        dataset,
        setDataset,
        diagnostics,
        setDiagnostics,
        selectedMethod,
        setSelectedMethod,
        alpha,
        setAlpha,
        alternative,
        setAlternative,
        delta,
        setDelta,
        seed,
        setSeed,
        analysisOutcome,
        setAnalysisOutcome,
        resetAll,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = (): WorkspaceState => {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace doit être utilisé au sein d'un WorkspaceProvider");
  }
  return context;
};
