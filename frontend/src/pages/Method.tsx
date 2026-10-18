import React, { useEffect, useState } from "react";
import { api } from "../api/endpoints";
import { MissingPrerequisite } from "../components/MissingPrerequisite";
import { WarningList } from "../components/WarningList";
import { useWorkspace } from "../state/workspaceState";
import { Alternative, Method, MethodCompatibility } from "../types/results";

export const MethodPage: React.FC = () => {
  const {
    dataset,
    diagnostics,
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
    setAnalysisOutcome,
    setCurrentStep,
  } = useWorkspace();

  const [compatibilities, setCompatibilities] = useState<MethodCompatibility[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!dataset) return;
    const loadCompatibility = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await api.getCompatibility({
          group_a: dataset.group_a,
          group_b: dataset.group_b,
          metric_type: dataset.metric_type,
          unit: dataset.unit,
        });
        setCompatibilities(res.methods);
        // Pré-sélectionner la méthode recommandée si aucune n'est sélectionnée
        const rec = res.methods.find((m) => m.is_recommended);
        if (rec && !selectedMethod) {
          setSelectedMethod(rec.method);
        } else if (!selectedMethod && res.methods.some((m) => m.compatible)) {
          setSelectedMethod(res.methods.find((m) => m.compatible)!.method);
        }
      } catch (err: any) {
        setError(err.message || "Erreur lors du calcul des compatibilités");
      } finally {
        setLoading(false);
      }
    };
    loadCompatibility();
  }, [dataset]);

  if (!dataset) {
    return (
      <MissingPrerequisite
        title="Aucun jeu de données pour choisir une méthode"
        description="Vous devez d'abord charger un jeu de données à l'étape Dataset."
        requiredStep="dataset"
        requiredStepLabel="Dataset"
      />
    );
  }

  const handleLaunchAnalysis = async () => {
    if (!selectedMethod) return;
    try {
      setAnalyzing(true);
      setError(null);
      const outcome = await api.runAnalysis({
        method: selectedMethod,
        group_a: dataset.group_a,
        group_b: dataset.group_b,
        alpha,
        alternative,
        delta,
        unit: dataset.unit,
        seed,
      });
      setAnalysisOutcome(outcome);
      setCurrentStep("results");
    } catch (err: any) {
      setError(err.message || "Erreur lors de l'exécution de l'analyse");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>
          3. Sélection de la Méthode Statistique
        </h1>
        <p style={{ color: "#64748b", marginTop: "6px", fontSize: "0.95rem" }}>
          Choisissez explicitement votre méthode d'inférence parmi celles compatibles avec vos données.
        </p>
      </div>

      {error && (
        <div style={{ backgroundColor: "#fef2f2", color: "#b91c1c", padding: "12px", borderRadius: "8px", marginBottom: "16px" }}>
          ⚠️ {error}
        </div>
      )}

      {loading && <div style={{ color: "#64748b" }}>Évaluation de la compatibilité des méthodes...</div>}

      {/* Grille des méthodes */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px", marginBottom: "28px" }}>
        {compatibilities.map((c) => {
          const isSelected = selectedMethod === c.method;
          return (
            <div
              key={c.method}
              onClick={() => {
                if (c.compatible) setSelectedMethod(c.method);
              }}
              style={{
                backgroundColor: c.compatible ? "#ffffff" : "#f8fafc",
                borderRadius: "10px",
                border: "2px solid",
                borderColor: isSelected ? "#2563eb" : c.compatible ? "#e2e8f0" : "#cbd5e1",
                padding: "16px 20px",
                cursor: c.compatible ? "pointer" : "not-allowed",
                opacity: c.compatible ? 1 : 0.6,
                position: "relative",
                transition: "all 0.15s ease",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <span style={{ fontSize: "1.05rem", fontWeight: 700, color: c.compatible ? "#0f172a" : "#64748b" }}>
                  {c.method}
                </span>
                {c.is_recommended && (
                  <span
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      backgroundColor: "#dbeafe",
                      color: "#1d4ed8",
                      padding: "2px 8px",
                      borderRadius: "9999px",
                      textTransform: "uppercase",
                    }}
                  >
                    ★ Recommandée
                  </span>
                )}
                {!c.compatible && (
                  <span
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 600,
                      backgroundColor: "#fee2e2",
                      color: "#b91c1c",
                      padding: "2px 8px",
                      borderRadius: "9999px",
                    }}
                  >
                    Incompatible
                  </span>
                )}
              </div>

              {c.reason && (
                <div style={{ fontSize: "0.82rem", color: "#64748b", fontStyle: "italic", marginBottom: "8px" }}>
                  {c.reason}
                </div>
              )}

              {c.compatible && (
                <>
                  <div style={{ fontSize: "0.8rem", color: "#475569", marginBottom: "8px" }}>
                    <b>Hypothèses :</b> {c.assumptions.map((a) => a.code).join(", ")}
                  </div>
                  <WarningList warnings={c.warnings} />
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Paramètres de l'analyse */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "10px",
          border: "1px solid #e2e8f0",
          padding: "24px",
          marginBottom: "24px",
        }}
      >
        <h3 style={{ margin: "0 0 16px 0", fontSize: "1.1rem", color: "#1e293b" }}>
          Paramètres du protocole d'analyse
        </h3>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "20px", marginBottom: "20px" }}>
          {/* Seuil alpha */}
          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
              Seuil de significativité (α) :
            </label>
            <select
              value={alpha}
              onChange={(e) => setAlpha(parseFloat(e.target.value))}
              style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
            >
              <option value={0.01}>0.01 (1%)</option>
              <option value={0.05}>0.05 (5% - convention)</option>
              <option value={0.10}>0.10 (10%)</option>
            </select>
          </div>

          {/* Alternative */}
          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
              Hypothèse alternative :
            </label>
            <select
              value={alternative}
              onChange={(e) => setAlternative(e.target.value as Alternative)}
              style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
            >
              <option value="two_sided">Bilatérale (B ≠ A)</option>
              <option value="greater">Unilatérale droite (B &gt; A)</option>
              <option value="less">Unilatérale gauche (B &lt; A)</option>
            </select>
          </div>

          {/* Seuil delta */}
          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
              Seuil économique δ (optionnel) :
            </label>
            <input
              type="number"
              step="0.001"
              value={delta !== null && delta !== undefined ? delta : ""}
              onChange={(e) => setDelta(e.target.value ? parseFloat(e.target.value) : null)}
              placeholder="ex: 0.01 (binaire) ou 1.5 (continu)"
              style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
            />
            <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
              Alimente l'arbre d'interprétation pratique sans modifier le calcul.
            </span>
          </div>

          {/* Graine reproductible */}
          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#475569" }}>
              Graine aléatoire (seed) :
            </label>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(parseInt(e.target.value) || 0)}
              style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #cbd5e1", marginTop: "4px" }}
            />
          </div>
        </div>

        <button
          onClick={handleLaunchAnalysis}
          disabled={!selectedMethod || analyzing}
          style={{
            padding: "12px 28px",
            backgroundColor: "#2563eb",
            color: "#ffffff",
            border: "none",
            borderRadius: "8px",
            fontWeight: 700,
            fontSize: "1rem",
            cursor: "pointer",
            transition: "background-color 0.15s ease",
          }}
        >
          {analyzing ? "Calcul de l'analyse en cours..." : `Lancer l'analyse (${selectedMethod}) →`}
        </button>
      </div>
    </div>
  );
};
