import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceIntervalPlot } from "../components/ConfidenceIntervalPlot";
import { ResultsPage } from "../pages/Results";
import { WorkspaceProvider } from "../state/workspaceState";
import { AnalysisOutcome, FavorableDirection } from "../types/results";
import { makeOutcome } from "./fixtures";

const STORAGE_KEY = "ab_analysis_workspace_state_v1";

/** Délai de paiement : B − A = −2,76 j, IC [−3,99 ; −1,53] (B paie plus vite). */
function fasterPaymentOutcome(direction?: FavorableDirection): AnalysisOutcome {
  const outcome = makeOutcome();
  return {
    ...outcome,
    interpretation: direction ? { ...outcome.interpretation!, favorable_direction: direction } : null,
  };
}

function renderResults(state: Record<string, unknown>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  return render(
    <WorkspaceProvider>
      <ResultsPage />
    </WorkspaceProvider>,
  );
}

describe("ResultsPage — sens favorable", () => {
  it("lit un délai plus court comme une dégradation si plus haut = mieux (lecture naïve)", async () => {
    renderResults({ analysisOutcome: fasterPaymentOutcome("higher_is_better"), delta: 1 });
    expect(await screen.findByText(/Cas \(E\)/)).toBeInTheDocument();
    expect(screen.getByText(/plus haut = mieux/)).toBeInTheDocument();
  });

  it("lit un délai plus court comme une amélioration si plus bas = mieux", async () => {
    renderResults({ analysisOutcome: fasterPaymentOutcome("lower_is_better"), delta: 1 });
    expect(await screen.findByText(/Cas \(A\)/)).toBeInTheDocument();
    expect(screen.queryByText(/Cas \(E\)/)).not.toBeInTheDocument();
    expect(screen.getByText(/une différence B − A négative est une amélioration/)).toBeInTheDocument();
  });

  it("se rabat sur le sens de la session quand le serveur n'a pas renvoyé d'interprétation", async () => {
    renderResults({ analysisOutcome: fasterPaymentOutcome(), favorableDirection: "lower_is_better", delta: 3 });
    // Gain A − B ∈ [1,53 ; 3,99] chevauche δ = 3 et l'estimé (2,76) reste sous δ -> cas (b).
    expect(await screen.findByText(/Cas \(B\)/)).toBeInTheDocument();
  });
});

describe("ConfidenceIntervalPlot — sens favorable", () => {
  it("place le seuil du côté négatif quand plus bas = mieux", () => {
    render(
      <ConfidenceIntervalPlot
        confidenceInterval={{ level: 0.95, lower: -3.9861, upper: -1.5336, method: "welch_t_dist" }}
        estimate={-2.7598}
        delta={1}
        unit="jours"
        favorableDirection="lower_is_better"
      />,
    );
    expect(screen.getByText("−δ (−1)")).toBeInTheDocument();
  });
});
