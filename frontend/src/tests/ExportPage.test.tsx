import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/endpoints";
import { ExportPage } from "../pages/Export";
import { WorkspaceProvider } from "../state/workspaceState";
import { makeOutcome } from "./fixtures";

const STORAGE_KEY = "ab_analysis_workspace_state_v1";

function renderWithSession(state: Record<string, unknown>) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  return render(
    <WorkspaceProvider>
      <ExportPage />
    </WorkspaceProvider>,
  );
}

const dataset = {
  group_a: [28.3, 30.1],
  group_b: [15.0, 19.8],
  metric_type: "continuous",
  unit: "jours",
  report: { n_input: 4, n_retained: 4, n_excluded: 0, exclusions: [], warnings: [] },
};

describe("ExportPage", () => {
  beforeEach(() => {
    // jsdom n'implémente pas les URL d'objets.
    window.URL.createObjectURL = vi.fn(() => "blob:test");
    window.URL.revokeObjectURL = vi.fn();
    // Le clic sur le lien de téléchargement déclencherait une navigation non gérée par jsdom.
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  it("renvoie vers l'étape Méthode tant qu'aucune analyse n'existe", () => {
    renderWithSession({});
    expect(screen.getByText("Aucun résultat à exporter")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Méthode/ })).toBeInTheDocument();
  });

  it("propose les quatre exports quand un résultat et un dataset sont disponibles", async () => {
    renderWithSession({ analysisOutcome: makeOutcome(), dataset });

    expect(await screen.findByRole("button", { name: /Rapport PDF/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export JSON/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Résultat CSV/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Données CSV/ })).toBeInTheDocument();
    expect(screen.getByText("sha256:abc123")).toBeInTheDocument();
  });

  it("envoie le résultat à l'export CSV et déclenche le téléchargement", async () => {
    const spy = vi.spyOn(api, "exportResultCsv").mockResolvedValue(new Blob(["a,b"]));
    const outcome = makeOutcome();
    renderWithSession({ analysisOutcome: outcome, dataset });

    await userEvent.click(await screen.findByRole("button", { name: /Résultat CSV/ }));

    await waitFor(() => expect(spy).toHaveBeenCalledWith(outcome));
    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
  });

  it("exporte les observations avec l'unité du dataset comme nom de colonne", async () => {
    const spy = vi.spyOn(api, "exportDataCsv").mockResolvedValue(new Blob(["group,jours"]));
    renderWithSession({ analysisOutcome: makeOutcome(), dataset });

    await userEvent.click(await screen.findByRole("button", { name: /Données CSV/ }));

    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({ group_a: [28.3, 30.1], group_b: [15.0, 19.8], metric_name: "jours" }),
    );
  });

  it("affiche l'erreur renvoyée par l'API", async () => {
    vi.spyOn(api, "exportPdf").mockRejectedValue(new Error("Erreur de génération PDF"));
    renderWithSession({ analysisOutcome: makeOutcome(), dataset });

    await userEvent.click(await screen.findByRole("button", { name: /Rapport PDF/ }));

    expect(await screen.findByText(/Erreur de génération PDF/)).toBeInTheDocument();
  });
});
