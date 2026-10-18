import React, { useEffect, useState } from "react";
import { api } from "../api/endpoints";
import { MissingPrerequisite } from "../components/MissingPrerequisite";
import { WarningList } from "../components/WarningList";
import { useWorkspace } from "../state/workspaceState";

export const DiagnosticsPage: React.FC = () => {
  const { dataset, diagnostics, setDiagnostics, setCurrentStep } = useWorkspace();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!dataset || diagnostics) return;
    const fetchDiag = async () => {
      try {
        setLoading(true);
        setError(null);
        const diag = await api.getDiagnostics({
          group_a: dataset.group_a,
          group_b: dataset.group_b,
          metric_type: dataset.metric_type,
          unit: dataset.unit,
        });
        setDiagnostics(diag);
      } catch (err: any) {
        setError(err.message || "Erreur de calcul des diagnostics");
      } finally {
        setLoading(false);
      }
    };
    fetchDiag();
  }, [dataset, diagnostics, setDiagnostics]);

  if (!dataset) {
    return (
      <MissingPrerequisite
        title="Aucun jeu de données chargé"
        description="Vous devez d'abord importer un fichier CSV ou générer une expérience simulée à l'étape Dataset."
        requiredStep="dataset"
        requiredStepLabel="Dataset"
      />
    );
  }

  const rep = dataset.report;

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>
          2. Diagnostics de Santé Statistique
        </h1>
        <p style={{ color: "#64748b", marginTop: "6px", fontSize: "0.95rem" }}>
          Décrire et vérifier les données avant de sélectionner une méthode d'analyse.
        </p>
      </div>

      {error && (
        <div style={{ backgroundColor: "#fef2f2", color: "#b91c1c", padding: "12px", borderRadius: "8px", marginBottom: "16px" }}>
          ⚠️ {error}
        </div>
      )}

      {/* Reçu de normalisation */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "10px",
          border: "1px solid #e2e8f0",
          padding: "20px",
          marginBottom: "24px",
        }}
      >
        <h3 style={{ margin: "0 0 12px 0", fontSize: "1.05rem", color: "#1e293b" }}>
          Reçu de validation et d'exclusions
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px" }}>
          <div style={{ backgroundColor: "#f8fafc", padding: "12px", borderRadius: "8px" }}>
            <div style={{ fontSize: "0.75rem", color: "#64748b" }}>LIGNES TOTALES</div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#0f172a" }}>{rep.n_input}</div>
          </div>
          <div style={{ backgroundColor: "#f8fafc", padding: "12px", borderRadius: "8px" }}>
            <div style={{ fontSize: "0.75rem", color: "#64748b" }}>LIGNES RETENUES</div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#16a34a" }}>{rep.n_retained}</div>
          </div>
          <div style={{ backgroundColor: "#f8fafc", padding: "12px", borderRadius: "8px" }}>
            <div style={{ fontSize: "0.75rem", color: "#64748b" }}>LIGNES ÉCARTÉES</div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: rep.n_excluded > 0 ? "#dc2626" : "#64748b" }}>
              {rep.n_excluded} ({(rep.exclusion_rate * 100).toFixed(1)} %)
            </div>
          </div>
          <div style={{ backgroundColor: "#f8fafc", padding: "12px", borderRadius: "8px" }}>
            <div style={{ fontSize: "0.75rem", color: "#64748b" }}>SÉPARATEURS NORMALISÉS</div>
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#0f172a" }}>{rep.decimal_conversions}</div>
          </div>
        </div>

        {rep.exclusions.length > 0 && (
          <div style={{ marginTop: "16px" }}>
            <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569", marginBottom: "6px" }}>
              Motifs d'exclusion :
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              {rep.exclusions.map((exc, idx) => (
                <div key={idx} style={{ fontSize: "0.82rem", color: "#64748b" }}>
                  • <b>{exc.reason}</b> : {exc.count} ligne(s) écartée(s) (exemples lignes : {exc.sample_row_indices.join(", ")})
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {loading && <div style={{ color: "#64748b", margin: "20px 0" }}>Calcul des diagnostics en cours...</div>}

      {/* Résumé des groupes et des diagnostics */}
      {diagnostics && (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Cartes Groupe A et B */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
            {/* Groupe A */}
            <div
              style={{
                backgroundColor: "#ffffff",
                padding: "20px",
                borderRadius: "10px",
                border: "1px solid #e2e8f0",
              }}
            >
              <h3 style={{ margin: "0 0 12px 0", fontSize: "1.1rem", color: "#1e293b" }}>
                Groupe A (Contrôle)
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "0.9rem" }}>
                <div><b>Effectif (N) :</b> {diagnostics.group_a.n}</div>
                {diagnostics.metric_type === "binary" ? (
                  <>
                    <div><b>Succès :</b> {diagnostics.group_a.successes}</div>
                    <div><b>Taux de conversion :</b> {((diagnostics.group_a.rate || 0) * 100).toFixed(2)} %</div>
                  </>
                ) : (
                  <>
                    <div><b>Moyenne :</b> {diagnostics.group_a.mean?.toFixed(3)} {diagnostics.unit}</div>
                    <div><b>Écart-type :</b> {diagnostics.group_a.sd?.toFixed(3)}</div>
                    <div><b>Médiane :</b> {diagnostics.group_a.median?.toFixed(3)}</div>
                    {diagnostics.group_a.skewness !== null && (
                      <div><b>Asymétrie (skewness) :</b> {diagnostics.group_a.skewness?.toFixed(2)}</div>
                    )}
                    {diagnostics.group_a.outlier_count !== null && (
                      <div><b>Valeurs extrêmes :</b> {diagnostics.group_a.outlier_count}</div>
                    )}
                  </>
                )}
                {diagnostics.group_a.ci_lower !== null && diagnostics.group_a.ci_upper !== null && (
                  <div>
                    <b>IC 95% :</b> [{diagnostics.group_a.ci_lower?.toFixed(3)} ; {diagnostics.group_a.ci_upper?.toFixed(3)}]
                  </div>
                )}
              </div>
            </div>

            {/* Groupe B */}
            <div
              style={{
                backgroundColor: "#ffffff",
                padding: "20px",
                borderRadius: "10px",
                border: "1px solid #e2e8f0",
              }}
            >
              <h3 style={{ margin: "0 0 12px 0", fontSize: "1.1rem", color: "#1e293b" }}>
                Groupe B (Traitement)
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "0.9rem" }}>
                <div><b>Effectif (N) :</b> {diagnostics.group_b.n}</div>
                {diagnostics.metric_type === "binary" ? (
                  <>
                    <div><b>Succès :</b> {diagnostics.group_b.successes}</div>
                    <div><b>Taux de conversion :</b> {((diagnostics.group_b.rate || 0) * 100).toFixed(2)} %</div>
                  </>
                ) : (
                  <>
                    <div><b>Moyenne :</b> {diagnostics.group_b.mean?.toFixed(3)} {diagnostics.unit}</div>
                    <div><b>Écart-type :</b> {diagnostics.group_b.sd?.toFixed(3)}</div>
                    <div><b>Médiane :</b> {diagnostics.group_b.median?.toFixed(3)}</div>
                    {diagnostics.group_b.skewness !== null && (
                      <div><b>Asymétrie (skewness) :</b> {diagnostics.group_b.skewness?.toFixed(2)}</div>
                    )}
                    {diagnostics.group_b.outlier_count !== null && (
                      <div><b>Valeurs extrêmes :</b> {diagnostics.group_b.outlier_count}</div>
                    )}
                  </>
                )}
                {diagnostics.group_b.ci_lower !== null && diagnostics.group_b.ci_upper !== null && (
                  <div>
                    <b>IC 95% :</b> [{diagnostics.group_b.ci_lower?.toFixed(3)} ; {diagnostics.group_b.ci_upper?.toFixed(3)}]
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Comparaison et Équilibre */}
          <div
            style={{
              backgroundColor: "#ffffff",
              padding: "20px",
              borderRadius: "10px",
              border: "1px solid #e2e8f0",
            }}
          >
            <h3 style={{ margin: "0 0 12px 0", fontSize: "1.05rem", color: "#1e293b" }}>
              Équilibre des groupes et écarts observés (B − A)
            </h3>
            <div style={{ display: "flex", gap: "24px", flexWrap: "wrap", fontSize: "0.9rem" }}>
              <div>
                <b>Ratio d'effectifs :</b> {(diagnostics.balance.ratio * 100).toFixed(1)} % (N_A={diagnostics.balance.n_a}, N_B={diagnostics.balance.n_b})
              </div>
              {diagnostics.metric_type === "binary" ? (
                <>
                  <div><b>Différence brute :</b> {(((diagnostics.comparison.absolute_difference || 0)) * 100).toFixed(2)} pp</div>
                  {diagnostics.comparison.relative_lift !== null && (
                    <div><b>Lift relatif :</b> {(((diagnostics.comparison.relative_lift || 0)) * 100).toFixed(2)} %</div>
                  )}
                  {diagnostics.comparison.odds_ratio !== null && (
                    <div><b>Odds ratio :</b> {diagnostics.comparison.odds_ratio?.toFixed(3)}</div>
                  )}
                </>
              ) : (
                <>
                  <div><b>Différence de moyennes :</b> {diagnostics.comparison.mean_difference?.toFixed(3)} {diagnostics.unit}</div>
                  <div><b>Différence de médianes :</b> {diagnostics.comparison.median_difference?.toFixed(3)} {diagnostics.unit}</div>
                  {diagnostics.comparison.variance_ratio !== null && (
                    <div><b>Ratio des variances (max/min) :</b> {diagnostics.comparison.variance_ratio?.toFixed(2)}</div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Avertissements */}
          {diagnostics.warnings.length > 0 && (
            <div>
              <h3 style={{ fontSize: "1rem", color: "#1e293b", marginBottom: "8px" }}>
                Avertissements de qualité statistique détectés :
              </h3>
              <WarningList warnings={diagnostics.warnings} />
            </div>
          )}

          <div style={{ marginTop: "12px" }}>
            <button
              onClick={() => setCurrentStep("method")}
              style={{
                padding: "10px 24px",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontWeight: 600,
                fontSize: "0.95rem",
                cursor: "pointer",
              }}
            >
              Étape suivante : Choix de la Méthode →
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
