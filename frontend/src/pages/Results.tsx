import React from "react";
import { MissingPrerequisite } from "../components/MissingPrerequisite";
import { ResultCard } from "../components/ResultCard";
import { useWorkspace } from "../state/workspaceState";

export const ResultsPage: React.FC = () => {
  const {
    analysisOutcome,
    delta,
    setDelta,
    setCurrentStep,
  } = useWorkspace();

  if (!analysisOutcome) {
    return (
      <MissingPrerequisite
        title="Aucun résultat d'analyse disponible"
        description="Veuillez d'abord sélectionner et exécuter une méthode d'analyse à l'étape Méthode."
        requiredStep="method"
        requiredStepLabel="Méthode"
      />
    );
  }

  const { result, interpretation } = analysisOutcome;

  // Calcul dynamique de l'interprétation côté client si delta varie sans relancer le calcul complet
  const computeLocalCase = (d: number | null): "a" | "b" | "c" | "d" | "e" | null => {
    const ci = result.confidence_interval;
    if (ci.lower === null || ci.upper === null) return null;
    if (ci.upper < 0) return "e";
    if (d === null) return null;
    const containsZero = ci.lower <= 0 && ci.upper >= 0;
    if (containsZero) {
      if (ci.lower >= -d && ci.upper <= d) return "c";
      return "d";
    }
    if (ci.lower >= d) return "a";
    if (ci.upper <= d) return "b";
    return result.estimate.value >= d ? "a" : "b";
  };

  const activeCase = computeLocalCase(delta);

  const getCaseInfo = (c: "a" | "b" | "c" | "d" | "e" | null) => {
    switch (c) {
      case "a":
        return {
          title: "Cas (A) : Significatif ET Pertinent",
          recommendation: "Déployer la variante B en production.",
          color: "#16a34a",
          bg: "#f0fdf4",
          border: "#bbf7d0",
          desc: "L'amélioration observée est statistiquement démontrée et dépasse votre seuil de rentabilité économique.",
        };
      case "b":
        return {
          title: "Cas (B) : Significatif mais Négligeable",
          recommendation: "Ne pas déployer la variante B.",
          color: "#d97706",
          bg: "#fffbeb",
          border: "#fde68a",
          desc: "L'effet existe réellement mais il est trop faible pour compenser le coût de maintenance ou de déploiement.",
        };
      case "c":
        return {
          title: "Cas (C) : Non concluant, gros effet exclu",
          recommendation: "Arrêter l'expérimentation ; variante B sans valeur ajoutée.",
          color: "#475569",
          bg: "#f8fafc",
          border: "#e2e8f0",
          desc: "L'intervalle de confiance est resserré autour de zéro : nous avons la certitude que B n'apporte aucun gain économique suffisant.",
        };
      case "d":
        return {
          title: "Cas (D) : Non concluant, étude trop imprécise",
          recommendation: "Poursuivre ou relancer avec un effectif plus grand.",
          color: "#7c3aed",
          bg: "#f5f3ff",
          border: "#ddd6fe",
          desc: "L'intervalle de confiance dépasse le seuil delta : les données actuelles ne permettent pas de trancher avec certitude.",
        };
      case "e":
        return {
          title: "Cas (E) : Effet Négatif Significatif",
          recommendation: "Rejeter impérativement la variante B (dégradation).",
          color: "#dc2626",
          bg: "#fef2f2",
          border: "#fecaca",
          desc: "La variante B dégrade significativement les performances par rapport au contrôle A.",
        };
      default:
        return null;
    }
  };

  const caseInfo = getCaseInfo(activeCase);

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>
          4. Résultats de l'Analyse A/B
        </h1>
        <p style={{ color: "#64748b", marginTop: "6px", fontSize: "0.95rem" }}>
          L'évaluation conjointe de la significativité statistique, de l'amplitude métier et de l'impact économique.
        </p>
      </div>

      {/* Résultat statistique complet */}
      <ResultCard result={result} delta={delta} />

      {/* Ajustement interactif du seuil delta */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "10px",
          border: "1px solid #e2e8f0",
          padding: "20px",
          margin: "24px 0",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div>
            <h3 style={{ margin: 0, fontSize: "1rem", color: "#1e293b" }}>
              Seuil de pertinence pratique (δ)
            </h3>
            <span style={{ fontSize: "0.82rem", color: "#64748b" }}>
              Modifiez le seuil économique sans recalculer les statistiques pour ajuster la décision métier.
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "#334155" }}>δ =</span>
            <input
              type="number"
              step="0.001"
              value={delta !== null && delta !== undefined ? delta : ""}
              onChange={(e) => setDelta(e.target.value ? parseFloat(e.target.value) : null)}
              placeholder="ex: 0.01"
              style={{
                width: "100px",
                padding: "6px 10px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                fontFamily: "monospace",
                fontWeight: 600,
              }}
            />
          </div>
        </div>

        {/* Bloc d'interprétation déterministe */}
        {caseInfo ? (
          <div
            style={{
              backgroundColor: caseInfo.bg,
              border: `1px solid ${caseInfo.border}`,
              borderRadius: "8px",
              padding: "16px",
              marginTop: "14px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.95rem", fontWeight: 700, color: caseInfo.color }}>
                {caseInfo.title}
              </span>
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  backgroundColor: caseInfo.color,
                  color: "#ffffff",
                  padding: "3px 8px",
                  borderRadius: "9999px",
                }}
              >
                CAS {activeCase?.toUpperCase()}
              </span>
            </div>
            <p style={{ margin: "6px 0 10px 0", fontSize: "0.88rem", color: "#334155", lineHeight: 1.45 }}>
              {caseInfo.desc}
            </p>
            <div style={{ fontSize: "0.9rem", fontWeight: 700, color: caseInfo.color }}>
              Recommandation : {caseInfo.recommendation}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: "0.85rem", color: "#64748b", fontStyle: "italic", marginTop: "10px" }}>
            Saisissez un seuil δ ci-dessus pour situer l'intervalle de confiance et obtenir une recommandation d'action (cas A à D).
          </div>
        )}
      </div>

      {/* Navigation vers Export */}
      <div>
        <button
          onClick={() => setCurrentStep("export")}
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
          Étape suivante : Exporter le Rapport PDF →
        </button>
      </div>
    </div>
  );
};
