import React, { useState } from "react";
import { api, PreviewResponse } from "../api/endpoints";
import { useWorkspace } from "../state/workspaceState";
import { ColumnProfiles, MetricType } from "../types/dataset";

export const DatasetPage: React.FC = () => {
  const { setDataset, setDiagnostics, setCurrentStep } = useWorkspace();

  const [activeTab, setActiveTab] = useState<"csv" | "simulate">("csv");
  const [csvText, setCsvText] = useState<string>("");
  const [preview, setPreview] = useState<PreviewResponse | null>(null);

  // Sélections de colonnes
  const [groupCol, setGroupCol] = useState<string>("");
  const [metricCol, setMetricCol] = useState<string>("");
  const [profiles, setProfiles] = useState<ColumnProfiles | null>(null);

  // Mappings de l'analyste
  const [groupA, setGroupA] = useState<string>("");
  const [groupB, setGroupB] = useState<string>("");
  const [metricType, setMetricType] = useState<MetricType>("binary");
  const [binarySuccess, setBinarySuccess] = useState<string>("1");
  const [binaryFailure, setBinaryFailure] = useState<string>("0");
  const [unit, setUnit] = useState<string>("proportion");
  const [decimalSeparator, setDecimalSeparator] = useState<"." | ",">(".");
  const [excludeUnmapped, setExcludeUnmapped] = useState<boolean>(false);

  // Paramètres de simulation
  const [simType, setSimType] = useState<"binary" | "continuous">("binary");
  const [simRateA, setSimRateA] = useState<number>(0.111);
  const [simRateB, setSimRateB] = useState<number>(0.124);
  const [simMeanA, setSimMeanA] = useState<number>(10.0);
  const [simMeanB, setSimMeanB] = useState<number>(12.0);
  const [simSdA, setSimSdA] = useState<number>(2.0);
  const [simSdB, setSimSdB] = useState<number>(2.0);
  const [simNA, setSimNA] = useState<number>(500);
  const [simNB, setSimNB] = useState<number>(500);
  const [simSeed, setSimSeed] = useState<number>(42);

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (evt) => {
      const text = evt.target?.result as string;
      setCsvText(text);
      await loadPreview(text);
    };
    reader.readAsText(file);
  };

  const loadPreview = async (text: string) => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.previewCsv(text);
      setPreview(res);
      if (res.columns.length >= 2) {
        setGroupCol(res.columns[0]);
        setMetricCol(res.columns[1]);
      }
    } catch (err: any) {
      setError(err.message || "Erreur de lecture du CSV");
    } finally {
      setLoading(false);
    }
  };

  const handleProfileColumns = async () => {
    if (!csvText || !groupCol || !metricCol) return;
    try {
      setLoading(true);
      setError(null);
      // Extraire colonnes
      const lines = csvText.trim().split("\n");
      const headers = lines[0].split(preview?.delimiter || ",");
      const gIdx = headers.indexOf(groupCol);
      const mIdx = headers.indexOf(metricCol);

      const gVals: any[] = [];
      const mVals: any[] = [];
      for (let i = 1; i < lines.length; i++) {
        const parts = lines[i].split(preview?.delimiter || ",");
        gVals.push(parts[gIdx]);
        mVals.push(parts[mIdx]);
      }

      const prof = await api.profileColumns({
        group_values: gVals,
        metric_values: mVals,
        group_column_name: groupCol,
        metric_column_name: metricCol,
      });
      setProfiles(prof);

      // Pré-remplir les mappings à partir du profil
      if (prof.group_profile.top_values.length >= 2) {
        setGroupA(prof.group_profile.top_values[0].value);
        setGroupB(prof.group_profile.top_values[1].value);
      }
      if (prof.metric_profile.proposed_type === "continuous") {
        setMetricType("continuous");
        setUnit(prof.metric_profile.proposed_unit || "sec");
      } else {
        setMetricType("binary");
        setUnit("proportion");
      }
      setDecimalSeparator(prof.metric_profile.decimal_separator as "." | ",");
    } catch (err: any) {
      setError(err.message || "Erreur de profilage");
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (!csvText || !groupA || !groupB) {
      setError("Veuillez sélectionner les valeurs de référence pour les groupes A et B.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const lines = csvText.trim().split("\n");
      const headers = lines[0].split(preview?.delimiter || ",");
      const gIdx = headers.indexOf(groupCol);
      const mIdx = headers.indexOf(metricCol);

      const gVals: any[] = [];
      const mVals: any[] = [];
      for (let i = 1; i < lines.length; i++) {
        const parts = lines[i].split(preview?.delimiter || ",");
        gVals.push(parts[gIdx]);
        mVals.push(parts[mIdx]);
      }

      const imported = await api.importDataset({
        group_values: gVals,
        metric_values: mVals,
        group_a_value: groupA,
        group_b_value: groupB,
        metric_type: metricType,
        binary_success_value: metricType === "binary" ? binarySuccess : null,
        binary_failure_value: metricType === "binary" ? binaryFailure : null,
        unit: metricType === "continuous" ? unit : "proportion",
        decimal_separator: decimalSeparator,
        group_column_name: groupCol,
        metric_column_name: metricCol,
        exclude_unmapped_groups: excludeUnmapped,
      });

      setDataset(imported);
      setDiagnostics(null); // Force recalcul des diagnostics
      setCurrentStep("diagnostics");
    } catch (err: any) {
      setError(err.message || "Erreur d'importation");
    } finally {
      setLoading(false);
    }
  };

  const handleSimulate = async () => {
    try {
      setLoading(true);
      setError(null);
      if (simType === "binary") {
        const sim = await api.simulateBinary({
          rate_a: simRateA,
          rate_b: simRateB,
          n_a: simNA,
          n_b: simNB,
          seed: simSeed,
        });
        // Importer directement
        const imported = await api.importDataset({
          group_values: sim.group_column,
          metric_values: sim.metric_column,
          group_a_value: sim.group_a_value,
          group_b_value: sim.group_b_value,
          metric_type: "binary",
          binary_success_value: "1",
          binary_failure_value: "0",
          unit: "proportion",
        });
        setDataset(imported);
      } else {
        const sim = await api.simulateContinuous({
          mean_a: simMeanA,
          mean_b: simMeanB,
          sd_a: simSdA,
          sd_b: simSdB,
          n_a: simNA,
          n_b: simNB,
          seed: simSeed,
          unit: "sec",
        });
        const imported = await api.importDataset({
          group_values: sim.group_column,
          metric_values: sim.metric_column,
          group_a_value: sim.group_a_value,
          group_b_value: sim.group_b_value,
          metric_type: "continuous",
          unit: "sec",
        });
        setDataset(imported);
      }
      setDiagnostics(null);
      setCurrentStep("diagnostics");
    } catch (err: any) {
      setError(err.message || "Erreur lors de la simulation");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>
          1. Import & Déclaration des Données
        </h1>
        <p style={{ color: "#64748b", marginTop: "6px", fontSize: "0.95rem" }}>
          Importez votre fichier CSV ou générez une expérience simulée contrôlée.
        </p>
      </div>

      {/* Onglets CSV / Simulation */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "24px" }}>
        <button
          onClick={() => setActiveTab("csv")}
          style={{
            padding: "8px 18px",
            borderRadius: "6px",
            border: "1px solid",
            borderColor: activeTab === "csv" ? "#2563eb" : "#cbd5e1",
            backgroundColor: activeTab === "csv" ? "#eff6ff" : "#ffffff",
            color: activeTab === "csv" ? "#1d4ed8" : "#475569",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          📂 Fichier CSV
        </button>
        <button
          onClick={() => setActiveTab("simulate")}
          style={{
            padding: "8px 18px",
            borderRadius: "6px",
            border: "1px solid",
            borderColor: activeTab === "simulate" ? "#2563eb" : "#cbd5e1",
            backgroundColor: activeTab === "simulate" ? "#eff6ff" : "#ffffff",
            color: activeTab === "simulate" ? "#1d4ed8" : "#475569",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          🎲 Données Simulées
        </button>
      </div>

      {error && (
        <div
          style={{
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#b91c1c",
            padding: "12px 16px",
            borderRadius: "8px",
            marginBottom: "20px",
            fontSize: "0.9rem",
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {activeTab === "csv" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Upload card */}
          <div
            style={{
              backgroundColor: "#ffffff",
              padding: "24px",
              borderRadius: "10px",
              border: "1px solid #e2e8f0",
            }}
          >
            <h3 style={{ margin: "0 0 12px 0", fontSize: "1rem", color: "#1e293b" }}>
              Téléverser votre CSV
            </h3>
            <input
              type="file"
              accept=".csv,.txt"
              onChange={handleFileUpload}
              style={{ marginBottom: "16px" }}
            />
            <div style={{ fontSize: "0.85rem", color: "#64748b" }}>
              Ou collez le contenu CSV ci-dessous :
            </div>
            <textarea
              rows={4}
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              placeholder="visitor_id,variant,converted&#10;1,control,0&#10;2,treatment,1..."
              style={{
                width: "100%",
                marginTop: "8px",
                padding: "10px",
                fontFamily: "monospace",
                fontSize: "0.85rem",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                boxSizing: "border-box",
              }}
            />
            <button
              onClick={() => loadPreview(csvText)}
              disabled={!csvText || loading}
              style={{
                marginTop: "12px",
                padding: "8px 16px",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Analyser le CSV
            </button>
          </div>

          {/* Aperçu & Sélection des colonnes */}
          {preview && (
            <div
              style={{
                backgroundColor: "#ffffff",
                padding: "24px",
                borderRadius: "10px",
                border: "1px solid #e2e8f0",
              }}
            >
              <h3 style={{ margin: "0 0 12px 0", fontSize: "1rem", color: "#1e293b" }}>
                Aperçu ({preview.row_count} lignes, délimiteur : "{preview.delimiter}")
              </h3>
              <div style={{ display: "flex", gap: "20px", marginBottom: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
                    Colonne Groupe :
                  </label>
                  <select
                    value={groupCol}
                    onChange={(e) => setGroupCol(e.target.value)}
                    style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
                  >
                    {preview.columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
                    Colonne Métrique :
                  </label>
                  <select
                    value={metricCol}
                    onChange={(e) => setMetricCol(e.target.value)}
                    style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
                  >
                    {preview.columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ alignSelf: "flex-end" }}>
                  <button
                    onClick={handleProfileColumns}
                    disabled={loading}
                    style={{
                      padding: "8px 16px",
                      backgroundColor: "#0284c7",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "6px",
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    Profiler les colonnes
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Déclarations de l'analyste */}
          {profiles && (
            <div
              style={{
                backgroundColor: "#ffffff",
                padding: "24px",
                borderRadius: "10px",
                border: "1px solid #e2e8f0",
              }}
            >
              <h3 style={{ margin: "0 0 16px 0", fontSize: "1.05rem", color: "#1e293b" }}>
                Déclarations explicites de l'analyste
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
                <div>
                  <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
                    Groupe A (Contrôle / Référence) :
                  </label>
                  <input
                    type="text"
                    value={groupA}
                    onChange={(e) => setGroupA(e.target.value)}
                    style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
                    Groupe B (Traitement / Nouveauté) :
                  </label>
                  <input
                    type="text"
                    value={groupB}
                    onChange={(e) => setGroupB(e.target.value)}
                    style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
                <div>
                  <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
                    Type de métrique :
                  </label>
                  <select
                    value={metricType}
                    onChange={(e) => setMetricType(e.target.value as MetricType)}
                    style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
                  >
                    <option value="binary">Binaire (0/1, succès/échec)</option>
                    <option value="continuous">Continue (temps, revenus...)</option>
                  </select>
                </div>
                {metricType === "continuous" ? (
                  <div>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
                      Unité métier (obligatoire) :
                    </label>
                    <input
                      type="text"
                      value={unit}
                      onChange={(e) => setUnit(e.target.value)}
                      placeholder="ex: euros, secondes, clics"
                      style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
                    />
                  </div>
                ) : (
                  <div style={{ display: "flex", gap: "8px" }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: "0.8rem", color: "#475569" }}>Valeur Succès :</label>
                      <input
                        type="text"
                        value={binarySuccess}
                        onChange={(e) => setBinarySuccess(e.target.value)}
                        style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: "0.8rem", color: "#475569" }}>Valeur Échec :</label>
                      <input
                        type="text"
                        value={binaryFailure}
                        onChange={(e) => setBinaryFailure(e.target.value)}
                        style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", color: "#475569" }}>
                  <input
                    type="checkbox"
                    checked={excludeUnmapped}
                    onChange={(e) => setExcludeUnmapped(e.target.checked)}
                  />
                  Écarter les lignes appartenant à d'autres groupes non mappés (enregistré dans le rapport).
                </label>
              </div>

              <button
                onClick={handleImport}
                disabled={loading}
                style={{
                  padding: "10px 24px",
                  backgroundColor: "#16a34a",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  fontWeight: 600,
                  fontSize: "0.95rem",
                  cursor: "pointer",
                }}
              >
                Valider & Accéder aux Diagnostics →
              </button>
            </div>
          )}
        </div>
      ) : (
        /* Onglet Simulation */
        <div
          style={{
            backgroundColor: "#ffffff",
            padding: "24px",
            borderRadius: "10px",
            border: "1px solid #e2e8f0",
            maxWidth: "600px",
          }}
        >
          <h3 style={{ margin: "0 0 16px 0", fontSize: "1.05rem", color: "#1e293b" }}>
            Générateur d'expérience déterministe
          </h3>
          <div style={{ marginBottom: "16px" }}>
            <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>Type d'expérience :</label>
            <select
              value={simType}
              onChange={(e) => setSimType(e.target.value as any)}
              style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
            >
              <option value="binary">Binaire (taux de conversion)</option>
              <option value="continuous">Continue (moyennes & écarts-types)</option>
            </select>
          </div>

          {simType === "binary" ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
              <div>
                <label style={{ fontSize: "0.8rem", color: "#475569" }}>Taux A :</label>
                <input
                  type="number"
                  step="0.001"
                  value={simRateA}
                  onChange={(e) => setSimRateA(parseFloat(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "0.8rem", color: "#475569" }}>Taux B :</label>
                <input
                  type="number"
                  step="0.001"
                  value={simRateB}
                  onChange={(e) => setSimRateB(parseFloat(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                />
              </div>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
              <div>
                <label style={{ fontSize: "0.8rem", color: "#475569" }}>Moyenne A :</label>
                <input
                  type="number"
                  value={simMeanA}
                  onChange={(e) => setSimMeanA(parseFloat(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "0.8rem", color: "#475569" }}>Moyenne B :</label>
                <input
                  type="number"
                  value={simMeanB}
                  onChange={(e) => setSimMeanB(parseFloat(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
                />
              </div>
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px", marginBottom: "20px" }}>
            <div>
              <label style={{ fontSize: "0.8rem", color: "#475569" }}>N par groupe :</label>
              <input
                type="number"
                value={simNA}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  setSimNA(val);
                  setSimNB(val);
                }}
                style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
              />
            </div>
            <div>
              <label style={{ fontSize: "0.8rem", color: "#475569" }}>Graine (seed) :</label>
              <input
                type="number"
                value={simSeed}
                onChange={(e) => setSimSeed(parseInt(e.target.value))}
                style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1" }}
              />
            </div>
          </div>

          <button
            onClick={handleSimulate}
            disabled={loading}
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
            Générer & Analyser →
          </button>
        </div>
      )}
    </div>
  );
};
