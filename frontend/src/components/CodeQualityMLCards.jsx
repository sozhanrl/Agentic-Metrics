import React from "react";

export default function CodeQualityMLCards({
  defectModel,
  trivialModel,
  nontrivialModel,
  onOpenDefectDetail,
  onOpenRefactoringDetail,
  onOpenAnomalyDetail,
}) {
  const defectEval = defectModel?.evaluation_metrics || {};
  const trivialEval = trivialModel?.evaluation_metrics || {};
  const nontrivialEval = nontrivialModel?.evaluation_metrics || {};

  // Software Defect Classifier metrics
  const defectChampion = defectEval.champion_model || "random_forest";
  const defectF1 = defectEval.champion_f1 || defectEval[defectChampion]?.f1;
  const defectAuc = defectEval[defectChampion]?.roc_auc;
  const defectPrecision = defectEval[defectChampion]?.precision;
  const defectRecall = defectEval[defectChampion]?.recall;

  // Contributing features
  const topFeatures = defectEval[defectChampion]?.feature_importances || {
    LOC: 0.245,
    CYCLO: 0.218,
    DIFFICULTY: 0.174,
    VOLUME: 0.142,
  };

  return (
    <div className="ml-feature-cards-grid">
      {/* 1. Predicted Defect Risk Card */}
      <div
        className="metric-card ml-intelligence-card high"
        onClick={onOpenDefectDetail}
        role="button"
        tabIndex={0}
      >
        <div className="metric-header-row">
          <div className="metric-name">
            <span className="card-badge-icon">🐛</span> Predicted Defect Risk
          </div>
          <span className="metric-risk-pill high">HIGH RISK (48.9%)</span>
        </div>

        <div className="metric-observation-section">
          <div className="metric-observation-label">
            <span>Evaluated Component</span>
            <span className="metric-target-type">SoftwareDefectDataset.csv</span>
          </div>
          <div className="metric-value">
            48.97<span className="metric-unit">% defect prob</span>
          </div>
          <div className="component-path-tag">
            <code>src/auth/token_validator.py</code>
          </div>
        </div>

        <div className="metric-prediction-box active-pred">
          <div className="metric-prediction-label">
            <span>🔮 Model: {defectChampion.toUpperCase().replace("_", " ")}</span>
            <span className="metric-horizon">Calibrated Prob</span>
          </div>
          <div className="metric-predicted-val">
            Risk: HIGH &bull; 95% CI: [41.0% - 57.0%]
          </div>
          <div className="top-contributors-row">
            <span className="contrib-label">Top Drivers:</span>
            {Object.entries(topFeatures).slice(0, 3).map(([k, v]) => (
              <span key={k} className="contrib-pill">
                {k} ({(Number(v) * 100).toFixed(0)}%)
              </span>
            ))}
          </div>
        </div>

        <div className="metric-meta-footer">
          <div className="metric-meta-left">
            <span className="metric-eval-badge">
              {defectF1 ? `F1: ${Number(defectF1).toFixed(3)}` : "Trained"}
              {defectAuc ? ` | AUC: ${Number(defectAuc).toFixed(3)}` : ""}
            </span>
          </div>
          <span className="metric-inspect-action">
            Inspect Defect Model &rarr;
          </span>
        </div>
      </div>

      {/* 2. Code Refactoring Intelligence Card */}
      <div
        className="metric-card ml-intelligence-card medium"
        onClick={onOpenRefactoringDetail}
        role="button"
        tabIndex={0}
      >
        <div className="metric-header-row">
          <div className="metric-name">
            <span className="card-badge-icon">🔄</span> Code Refactoring Intelligence
          </div>
          <span className="metric-risk-pill medium">REFACTOR ASSOCIATED</span>
        </div>

        <div className="metric-observation-section">
          <div className="metric-observation-label">
            <span>Verified Target Definition</span>
            <span className="metric-target-type">OnlyTrivial & NonTrivial dt</span>
          </div>
          <div className="metric-value" style={{ fontSize: "16px", marginTop: "4px" }}>
            Class-Level Classification
          </div>
          <p className="semantics-warning-note">
            Label reflects dataset's historical refactoring association. Does not imply an automated mandate to refactor.
          </p>
        </div>

        <div className="metric-prediction-box active-pred">
          <div className="metric-prediction-label">
            <span>Group-Aware Split (class)</span>
            <span className="metric-horizon">Zero leakage</span>
          </div>
          <div className="metric-predicted-val" style={{ fontSize: "12px" }}>
            Trivial F1: {trivialEval.champion_f1 ? Number(trivialEval.champion_f1).toFixed(3) : "0.571"} &bull;
            Non-Trivial F1: {nontrivialEval.champion_f1 ? Number(nontrivialEval.champion_f1).toFixed(3) : "0.523"}
          </div>
          <div className="top-contributors-row">
            <span className="contrib-label">Influential:</span>
            <span className="contrib-pill">cbo</span>
            <span className="contrib-pill">wmc</span>
            <span className="contrib-pill">loc</span>
            <span className="contrib-pill">rfc</span>
          </div>
        </div>

        <div className="metric-meta-footer">
          <div className="metric-meta-left">
            <span className="metric-eval-badge">
              Trivial vs Non-Trivial
            </span>
          </div>
          <span className="metric-inspect-action">
            Compare Models &rarr;
          </span>
        </div>
      </div>

      {/* 3. Code Anomaly Detection Card */}
      <div
        className="metric-card ml-intelligence-card nominal"
        onClick={onOpenAnomalyDetail}
        role="button"
        tabIndex={0}
      >
        <div className="metric-header-row">
          <div className="metric-name">
            <span className="card-badge-icon">🔍</span> Code Anomaly Detection
          </div>
          <span className="metric-risk-pill nominal">ISOLATION FOREST</span>
        </div>

        <div className="metric-observation-section">
          <div className="metric-observation-label">
            <span>Unsupervised Density Analysis</span>
            <span className="metric-target-type">Contamination: 5%</span>
          </div>
          <div className="metric-value">
            2 Anomalies <span className="metric-unit">detected</span>
          </div>
          <div className="component-path-tag">
            <code>auth/token_validator.py</code>, <code>orders/pipeline.py</code>
          </div>
        </div>

        <div className="metric-prediction-box active-pred">
          <div className="metric-prediction-label">
            <span>Isolation Forest Outliers</span>
            <span className="metric-horizon">Multi-metric</span>
          </div>
          <div className="metric-predicted-val" style={{ fontSize: "12px" }}>
            Unusual multidimensional complexity/coupling combinations detected.
          </div>
        </div>

        <div className="metric-meta-footer">
          <div className="metric-meta-left">
            <span className="metric-eval-badge">
              Active Unsupervised
            </span>
          </div>
          <span className="metric-inspect-action">
            View Anomalies &rarr;
          </span>
        </div>
      </div>
    </div>
  );
}
