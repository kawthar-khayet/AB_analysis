import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceIntervalPlot } from "../components/ConfidenceIntervalPlot";
import { ResultCard } from "../components/ResultCard";
import { WarningList } from "../components/WarningList";
import { makeResult } from "./fixtures";

describe("ConfidenceIntervalPlot", () => {
  it("affiche l'estimation et les deux bornes", () => {
    render(
      <ConfidenceIntervalPlot
        confidenceInterval={{ level: 0.95, lower: -3.9861, upper: -1.5336, method: "welch_t_dist" }}
        estimate={-2.7598}
        unit="jours"
      />,
    );
    expect(screen.getByText("-2.7598")).toBeInTheDocument();
    expect(screen.getByText("-3.9861")).toBeInTheDocument();
    expect(screen.getByText("-1.5336")).toBeInTheDocument();
    expect(screen.getByText(/IC 95%/)).toBeInTheDocument();
    expect(screen.getByText("H0 (0)")).toBeInTheDocument();
  });

  it("marque le seuil économique δ quand il est fourni", () => {
    render(
      <ConfidenceIntervalPlot
        confidenceInterval={{ level: 0.95, lower: 0.01, upper: 0.04, method: "normal_approx_unpooled" }}
        estimate={0.025}
        delta={0.02}
        unit="proportion"
      />,
    );
    expect(screen.getByText("δ (0.02)")).toBeInTheDocument();
  });

  it("explique quand l'intervalle n'est pas disponible", () => {
    render(
      <ConfidenceIntervalPlot
        confidenceInterval={{ level: 0.95, lower: null, upper: null, method: null }}
        estimate={1}
        unit="jours"
      />,
    );
    expect(screen.getByText(/non disponible/)).toBeInTheDocument();
  });
});

describe("WarningList", () => {
  it("ne rend rien sans avertissement", () => {
    const { container } = render(<WarningList warnings={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("affiche le code, le message et l'alternative suggérée", () => {
    render(
      <WarningList
        warnings={[
          {
            code: "HIGH_SKEWNESS",
            severity: "warning",
            message: "Forte asymétrie observée.",
            suggested_alternative: "bootstrap",
          },
        ]}
      />,
    );
    expect(screen.getByText("HIGH_SKEWNESS")).toBeInTheDocument();
    expect(screen.getByText("Forte asymétrie observée.")).toBeInTheDocument();
    expect(screen.getByText(/Alternative suggérée : bootstrap/)).toBeInTheDocument();
  });
});

describe("ResultCard", () => {
  it("affiche la méthode, les hypothèses et une très petite p-value arrondie", () => {
    render(<ResultCard result={makeResult()} delta={2} />);
    expect(screen.getByText(/Méthode d'analyse : welch_t/)).toBeInTheDocument();
    expect(screen.getByText("Les moyennes des groupes A et B sont différentes.")).toBeInTheDocument();
    expect(screen.getByText("p < 0,001")).toBeInTheDocument();
    expect(screen.getByText(/Degrés de liberté : 1537.6/)).toBeInTheDocument();
  });

  it("signale une p-value absente plutôt que d'inventer une valeur", () => {
    render(<ResultCard result={makeResult({ p_value: null, p_value_source: null })} />);
    expect(screen.getByText("Non calculée")).toBeInTheDocument();
  });

  it("formate une p-value ordinaire avec 4 décimales", () => {
    render(<ResultCard result={makeResult({ p_value: 0.2015, decision: "fail_to_reject_null" })} />);
    expect(screen.getByText("p = 0.2015")).toBeInTheDocument();
  });
});
