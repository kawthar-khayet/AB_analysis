import React, { useState } from "react";
import { api } from "../api/endpoints";
import { MissingPrerequisite } from "../components/MissingPrerequisite";
import { useWorkspace } from "../state/workspaceState";

export const ExportPage: React.FC = () => {
  const { analysisOutcome, dataset } = useWorkspace();
  const [experimentName, setExperimentName] = useState<string>("Expérimentation A/B");
  const [author, setAuthor] = useState<string>("Analyste de Données");
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!analysisOutcome) {
    return (
      <MissingPrerequisite
        title="Aucun résultat à exporter"
        description="Vous devez d'abord exécuter une analyse pour générer un rapport PDF ou exporter vos données."
        requiredStep="method"
        requiredStepLabel="Méthode"
      />
    );
  }

  const method = analysisOutcome.result.method;

  // Télécharge un Blob renvoyé par l'API sous le nom de fichier donné.
  const download = async (kind: string, fetchBlob: () => Promise<Blob>, filename: string) => {
    try {
      setDownloading(kind);
      setError(null);
      const blob = await fetchBlob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || `Erreur de téléchargement (${kind})`);
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadPdf = () =>
    download(
      "pdf",
      () => api.exportPdf({ analysis: analysisOutcome, experiment_name: experimentName, author }),
      `rapport_ab_${method}.pdf`,
    );
  const handleDownloadJson = () =>
    download("json", () => api.exportJson(analysisOutcome), `resultat_ab_${method}.json`);
  const handleDownloadResultCsv = () =>
    download("csv", () => api.exportResultCsv(analysisOutcome), `resultat_ab_${method}.csv`);
  const handleDownloadDataCsv = () =>
    dataset &&
    download(
      "data",
      () =>
        api.exportDataCsv({
          group_a: dataset.group_a,
          group_b: dataset.group_b,
          metric_name: dataset.unit || "value",
        }),
      "donnees_analysees.csv",
    );

  const secondaryButton: React.CSSProperties = {
    padding: "10px 20px",
    backgroundColor: "#ffffff",
    color: "#334155",
    border: "1px solid #cbd5e1",
    borderRadius: "8px",
    fontWeight: 600,
    cursor: "pointer",
  };

  const res = analysisOutcome.result;

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>
          5. Export & Reproductibilité
        </h1>
        <p style={{ color: "#64748b", marginTop: "6px", fontSize: "0.95rem" }}>
          Exportez un rapport PDF autonome, le schéma JSON complet, ou le résultat et les données au format CSV.
        </p>
      </div>

      {error && (
        <div style={{ backgroundColor: "#fef2f2", color: "#b91c1c", padding: "12px", borderRadius: "8px", marginBottom: "16px" }}>
          ⚠️ {error}
        </div>
      )}

      {/* Paramètres du rapport */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "10px",
          border: "1px solid #e2e8f0",
          padding: "24px",
          marginBottom: "24px",
          maxWidth: "600px",
        }}
      >
        <h3 style={{ margin: "0 0 16px 0", fontSize: "1.05rem", color: "#1e293b" }}>
          Informations du rapport
        </h3>

        <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginBottom: "20px" }}>
          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
              Titre de l'expérience :
            </label>
            <input
              type="text"
              value={experimentName}
              onChange={(e) => setExperimentName(e.target.value)}
              style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
            />
          </div>

          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
              Auteur / Équipe :
            </label>
            <input
              type="text"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
            />
          </div>
        </div>

        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          <button
            onClick={handleDownloadPdf}
            disabled={downloading !== null}
            style={{
              padding: "10px 20px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {downloading === "pdf" ? "Génération du PDF..." : "📄 Télécharger le Rapport PDF"}
          </button>

          <button onClick={handleDownloadJson} disabled={downloading !== null} style={secondaryButton}>
            {downloading === "json" ? "Export..." : "{ } Export JSON"}
          </button>

          <button onClick={handleDownloadResultCsv} disabled={downloading !== null} style={secondaryButton}>
            {downloading === "csv" ? "Export..." : "📊 Résultat CSV"}
          </button>

          {dataset && (
            <button onClick={handleDownloadDataCsv} disabled={downloading !== null} style={secondaryButton}>
              {downloading === "data" ? "Export..." : "🗂️ Données CSV"}
            </button>
          )}
        </div>
      </div>

      {/* Récapitulatif de reproductibilité */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "10px",
          border: "1px solid #e2e8f0",
          padding: "20px",
          maxWidth: "600px",
        }}
      >
        <h4 style={{ margin: "0 0 10px 0", fontSize: "0.95rem", color: "#1e293b" }}>
          Garanties de Reproductibilité :
        </h4>
        <div style={{ fontSize: "0.82rem", color: "#475569", lineHeight: 1.6 }}>
          <div><b>Empreinte SHA-256 :</b> <code style={{ backgroundColor: "#f1f5f9", padding: "2px 6px", borderRadius: "4px" }}>{res.reproducibility.input_hash}</code></div>
          <div><b>Calculé à :</b> {res.reproducibility.computed_at}</div>
          {res.reproducibility.seed !== null && res.reproducibility.seed !== undefined && (
            <div><b>Graine aléatoire :</b> {res.reproducibility.seed}</div>
          )}
          <div><b>Contrat d'échange :</b> version {res.contract_version}</div>
        </div>
      </div>
    </div>
  );
};
