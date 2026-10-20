import React, { useState, useEffect, useCallback } from "react";
import { api } from "../api";

const RISK_COLORS = {
  CRITICAL: "#ff4757",
  HIGH: "#ff6b6b",
  MEDIUM: "#ffa502",
  LOW: "#2ed573",
};

const MODEL_ICONS = {
  random_forest: "🌲",
  xgboost: "⚡",
  logistic_regression: "📐",
  isolation_forest: "🔍",
};

function MetricBadge({ label, value, color }) {
  return (
    <div className="dataset-metric-badge" style={{ borderLeft: `3px solid ${color || "#6c5ce7"}` }}>
      <div className="badge-label">{label}</div>
      <div className="badge-value" style={{ color: color || "#a29bfe" }}>{value}</div>
    </div>
  );
}

function ConfusionMatrixDisplay({ matrix, labels }) {
  if (!matrix || matrix.length === 0) return null;
  return (
    <div className="confusion-matrix">
      <div className="cm-title">Confusion Matrix</div>
      <table className="cm-table">
        <thead>
          <tr>
            <th></th>
            {labels.map((l, i) => <th key={i}>Pred: {l}</th>)}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <td className="cm-row-label">Actual: {labels[i]}</td>
              {row.map((val, j) => (
                <td key={j} className={i === j ? "cm-diagonal" : "cm-off"}>{val}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FeatureImportanceChart({ importances, maxBars = 8 }) {
  if (!importances || Object.keys(importances).length === 0) return null;
  const sorted = Object.entries(importances)
    .sort((a, b) => b[1] - a[1])
    .slice(0, maxBars);
  const maxVal = sorted[0]?.[1] || 1;

  return (
    <div className="feature-importance-chart">
      {sorted.map(([name, val]) => (
        <div key={name} className="fi-row">
          <span className="fi-name">{name}</span>
          <div className="fi-bar-bg">
            <div
              className="fi-bar"
              style={{ width: `${(val / maxVal) * 100}%` }}
            />
          </div>
          <span className="fi-val">{(val * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

function ModelResultCard({ name, icon, metrics, labels, importances }) {
  const [expanded, setExpanded] = useState(false);
  if (!metrics || metrics.status === "unavailable") {
    return (
      <div className="model-result-card disabled">
        <div className="mrc-header">
          <span className="mrc-icon">{icon}</span>
          <span className="mrc-name">{name}</span>
          <span className="mrc-status unavailable">Unavailable</span>
        </div>
      </div>
    );
  }

  return (
    <div className="model-result-card">
      <div className="mrc-header" onClick={() => setExpanded(!expanded)}>
        <span className="mrc-icon">{icon}</span>
        <span className="mrc-name">{name}</span>
        <div className="mrc-metrics-row">
          <span className="mrc-pill" title="F1 Score">F1: {metrics.f1?.toFixed(4)}</span>
          <span className="mrc-pill" title="ROC-AUC">AUC: {metrics.roc_auc?.toFixed(4)}</span>
          <span className="mrc-pill" title="Precision">P: {metrics.precision?.toFixed(3)}</span>
          <span className="mrc-pill" title="Recall">R: {metrics.recall?.toFixed(3)}</span>
        </div>
        <span className="mrc-expand">{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && (
        <div className="mrc-details">
          <div className="mrc-detail-grid">
            <div><strong>Accuracy:</strong> {(metrics.accuracy * 100).toFixed(2)}%</div>
            <div><strong>Precision:</strong> {(metrics.precision * 100).toFixed(2)}%</div>
            <div><strong>Recall:</strong> {(metrics.recall * 100).toFixed(2)}%</div>
            <div><strong>F1 Score:</strong> {metrics.f1?.toFixed(4)}</div>
            <div><strong>ROC-AUC:</strong> {metrics.roc_auc?.toFixed(4)}</div>
          </div>
          <ConfusionMatrixDisplay matrix={metrics.confusion_matrix} labels={labels} />
          <FeatureImportanceChart importances={importances || metrics.feature_importances} />
        </div>
      )}
    </div>
  );
}

export default function DatasetMLPanel({ projectId }) {
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [trainMsg, setTrainMsg] = useState(null);
  const [activeTab, setActiveTab] = useState("defect");

  const [datasetStatus, setDatasetStatus] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [processStatus, setProcessStatus] = useState(null);
  const [devopsStatus, setDevopsStatus] = useState(null);

  // Prediction state
  const [defectInput, setDefectInput] = useState({
    LOC: 0.5, CYCLO: 0.5, LENGTH: 0.5, VOLUME: 0.5, DIFFICULTY: 0.5,
    INT_FAN_IN: 0.5, INT_FAN_OUT: 0.5, NUM_OPERATORS: 0.5, NUM_OPERANDS: 0.5, BRANCH_COUNT: 0.5,
  });
  const [defectResult, setDefectResult] = useState(null);
  const [predicting, setPredicting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statusRes, evalRes, procRes, devRes] = await Promise.all([
        api.getDatasetStatus().catch(() => null),
        api.getDatasetEvaluation().catch(() => null),
        api.getProcessDataStatus().catch(() => null),
        api.getDevopsDataStatus().catch(() => null),
      ]);
      setDatasetStatus(statusRes);
      setEvaluation(evalRes);
      setProcessStatus(procRes);
      setDevopsStatus(devRes);

      // Try loading comparison
      try {
        const compRes = await api.getRefactoringComparison();
        setComparison(compRes);
      } catch { setComparison(null); }
    } catch (err) {
      console.error("Dataset ML load error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleTrain = async (datasets) => {
    setTraining(true);
    setTrainMsg("Training dataset models... This may take 30-60 seconds for large datasets.");
    try {
      const res = await api.trainDatasetModels({ datasets });
      if (res.status === "success") {
        const pipelines = Object.keys(res.pipelines || {}).filter(k => res.pipelines[k]?.status === "success");
        setTrainMsg(`✅ Training completed! ${pipelines.length} pipeline(s) trained successfully in ${(res.duration_ms / 1000).toFixed(1)}s.`);
        await loadData();
      } else {
        setTrainMsg(`⚠ Training issue: ${JSON.stringify(res)}`);
      }
    } catch (err) {
      setTrainMsg(`❌ Training error: ${err.message}`);
    } finally {
      setTraining(false);
      setTimeout(() => setTrainMsg(null), 12000);
    }
  };

  const handleDefectPredict = async () => {
    setPredicting(true);
    try {
      const res = await api.predictDefectRisk(defectInput);
      setDefectResult(res);
    } catch (err) {
      setDefectResult({ error: err.message });
    } finally {
      setPredicting(false);
    }
  };

  if (loading) {
    return (
      <div className="dataset-ml-panel">
        <div className="loading-state">
          <div className="spinner" />
          <span>Loading Dataset ML Intelligence...</span>
        </div>
      </div>
    );
  }

  const defectEval = evaluation?.defect_classifier;
  const trivialEval = evaluation?.refactoring_trivial;
  const nontrivialEval = evaluation?.refactoring_nontrivial;

  return (
    <div className="dataset-ml-panel">
      {/* Header */}
      <div className="dml-header">
        <div className="dml-title">
          <span className="dml-icon">🔬</span>
          <h2>Dataset ML Intelligence</h2>
          <span className="dml-subtitle">Real CSV Dataset Training & Prediction</span>
        </div>
        <div className="dml-train-actions">
          <button
            className="btn-train-all"
            onClick={() => handleTrain(null)}
            disabled={training}
          >
            {training ? "⏳ Training..." : "🚀 Train All Datasets"}
          </button>
          <button
            className="btn-train-single"
            onClick={() => handleTrain(["defect"])}
            disabled={training}
          >
            Train Defect Only
          </button>
          <button
            className="btn-train-single"
            onClick={() => handleTrain(["trivial", "nontrivial"])}
            disabled={training}
          >
            Train Refactoring Only
          </button>
        </div>
      </div>

      {trainMsg && (
        <div className={`train-notification ${trainMsg.startsWith("✅") ? "success" : trainMsg.startsWith("❌") ? "error" : "info"}`}>
          {trainMsg}
        </div>
      )}

      {/* Status KPI Strip */}
      <div className="dml-kpi-strip">
        <MetricBadge
          label="Defect Classifier"
          value={datasetStatus?.defect_classifier?.trained ? `F1: ${datasetStatus.defect_classifier.champion_f1?.toFixed(4)}` : "Not Trained"}
          color={datasetStatus?.defect_classifier?.trained ? "#2ed573" : "#636e72"}
        />
        <MetricBadge
          label="Trivial Refactoring"
          value={datasetStatus?.refactoring_trivial?.trained ? `F1: ${datasetStatus.refactoring_trivial.champion_f1?.toFixed(4)}` : "Not Trained"}
          color={datasetStatus?.refactoring_trivial?.trained ? "#0984e3" : "#636e72"}
        />
        <MetricBadge
          label="Non-Trivial Refactoring"
          value={datasetStatus?.refactoring_nontrivial?.trained ? `F1: ${datasetStatus.refactoring_nontrivial.champion_f1?.toFixed(4)}` : "Not Trained"}
          color={datasetStatus?.refactoring_nontrivial?.trained ? "#6c5ce7" : "#636e72"}
        />
        <MetricBadge
          label="Process Models"
          value={processStatus?.sufficient_for_training ? "Active" : "No Data"}
          color={processStatus?.sufficient_for_training ? "#2ed573" : "#636e72"}
        />
        <MetricBadge
          label="DevOps Models"
          value={devopsStatus?.sufficient_for_training ? "Active" : "No Data"}
          color={devopsStatus?.sufficient_for_training ? "#2ed573" : "#636e72"}
        />
      </div>

      {/* Tab Navigation */}
      <div className="dml-tabs">
        {[
          { key: "defect", label: "🐛 Defect Prediction", active: !!defectEval?.champion_model },
          { key: "refactoring", label: "🔄 Refactoring Intel", active: !!trivialEval?.champion_model },
          { key: "comparison", label: "📊 Model Comparison", active: !!comparison },
          { key: "predict", label: "🎯 Live Prediction", active: !!defectEval?.champion_model },
          { key: "process_devops", label: "⚙ Process & DevOps", active: true },
        ].map(t => (
          <button
            key={t.key}
            className={`dml-tab ${activeTab === t.key ? "active" : ""} ${!t.active ? "dim" : ""}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="dml-content">
        {/* ==== DEFECT TAB ==== */}
        {activeTab === "defect" && (
          <div className="dml-section">
            <h3>Software Defect Prediction <span className="section-tag">SoftwareDefectDataset.csv</span></h3>
            {!defectEval || defectEval.status === "not_trained" ? (
              <div className="empty-state-card">
                <p>🔧 Defect classifier has not been trained yet.</p>
                <p>Click <strong>"Train All Datasets"</strong> or <strong>"Train Defect Only"</strong> to begin.</p>
                <p className="subtle">Dataset: SoftwareDefectDataset.csv (1,000 software components × 10 Halstead/McCabe metrics)</p>
              </div>
            ) : (
              <>
                <div className="dataset-info-bar">
                  <span>📁 {defectEval.dataset?.name}</span>
                  <span>📏 {defectEval.dataset?.total_samples?.toLocaleString()} samples</span>
                  <span>🏆 Champion: {defectEval.champion_model}</span>
                  <span>🎯 F1: {defectEval.champion_f1?.toFixed(4)}</span>
                  <span>📐 Split: {defectEval.dataset?.splitting_strategy}</span>
                </div>
                <div className="model-cards-grid">
                  <ModelResultCard
                    name="Random Forest"
                    icon={MODEL_ICONS.random_forest}
                    metrics={defectEval.random_forest}
                    labels={["Non-Defective", "Defective"]}
                    importances={defectEval.random_forest?.feature_importances}
                  />
                  <ModelResultCard
                    name="XGBoost"
                    icon={MODEL_ICONS.xgboost}
                    metrics={defectEval.xgboost}
                    labels={["Non-Defective", "Defective"]}
                    importances={defectEval.xgboost?.feature_importances}
                  />
                  <ModelResultCard
                    name="Logistic Regression"
                    icon={MODEL_ICONS.logistic_regression}
                    metrics={defectEval.logistic_regression}
                    labels={["Non-Defective", "Defective"]}
                    importances={defectEval.logistic_regression?.feature_importances}
                  />
                </div>
                {defectEval.isolation_forest && (
                  <div className="anomaly-summary-card">
                    <h4>🔍 Isolation Forest (Unsupervised Anomaly Detection)</h4>
                    <div className="anomaly-stats">
                      <span>Total: {defectEval.isolation_forest.total_samples}</span>
                      <span>Anomalies: {defectEval.isolation_forest.anomalies_detected}</span>
                      <span>Rate: {(defectEval.isolation_forest.anomaly_rate * 100).toFixed(1)}%</span>
                      <span>Contamination: {defectEval.isolation_forest.contamination}</span>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ==== REFACTORING TAB ==== */}
        {activeTab === "refactoring" && (
          <div className="dml-section">
            <h3>Code Refactoring Intelligence</h3>
            <div className="refactoring-note">
              <strong>Label Semantics:</strong> The <code>refactoring</code> column indicates whether a record is
              associated with a refactoring operation (1) or not (0). This does <em>not</em> automatically mean
              refactoring <em>should</em> be performed — it reflects the dataset's observed label definition.
            </div>

            {/* Trivial */}
            <div className="refactoring-subsection">
              <h4>📂 Trivial Refactoring <span className="section-tag">OnlyTrivial_dt.csv</span></h4>
              {!trivialEval || trivialEval.status === "not_trained" ? (
                <div className="empty-state-card">
                  <p>Not trained. Click <strong>"Train Refactoring Only"</strong> to begin.</p>
                  <p className="subtle">Dataset: OnlyTrivial_dt.csv (232,468 rows × 53 columns)</p>
                </div>
              ) : (
                <>
                  <div className="dataset-info-bar">
                    <span>📏 {trivialEval.dataset?.total_samples?.toLocaleString()} samples (from 232,468)</span>
                    <span>🏆 {trivialEval.champion_model}</span>
                    <span>🎯 F1: {trivialEval.champion_f1?.toFixed(4)}</span>
                    <span>📐 {trivialEval.dataset?.splitting_strategy}</span>
                  </div>
                  <div className="model-cards-grid">
                    <ModelResultCard name="Random Forest" icon="🌲" metrics={trivialEval.random_forest} labels={["No Refactoring", "Refactoring"]} />
                    <ModelResultCard name="XGBoost" icon="⚡" metrics={trivialEval.xgboost} labels={["No Refactoring", "Refactoring"]} />
                    <ModelResultCard name="Logistic Regression" icon="📐" metrics={trivialEval.logistic_regression} labels={["No Refactoring", "Refactoring"]} />
                  </div>
                </>
              )}
            </div>

            {/* Non-Trivial */}
            <div className="refactoring-subsection">
              <h4>📂 Non-Trivial Refactoring <span className="section-tag">OnlyNonTrivial_dt.csv</span></h4>
              {!nontrivialEval || nontrivialEval.status === "not_trained" ? (
                <div className="empty-state-card">
                  <p>Not trained. Click <strong>"Train Refactoring Only"</strong> to begin.</p>
                  <p className="subtle">Dataset: OnlyNonTrivial_dt.csv (509,426 rows × 53 columns)</p>
                </div>
              ) : (
                <>
                  <div className="dataset-info-bar">
                    <span>📏 {nontrivialEval.dataset?.total_samples?.toLocaleString()} samples (from 509,426)</span>
                    <span>🏆 {nontrivialEval.champion_model}</span>
                    <span>🎯 F1: {nontrivialEval.champion_f1?.toFixed(4)}</span>
                    <span>📐 {nontrivialEval.dataset?.splitting_strategy}</span>
                  </div>
                  <div className="model-cards-grid">
                    <ModelResultCard name="Random Forest" icon="🌲" metrics={nontrivialEval.random_forest} labels={["No Refactoring", "Refactoring"]} />
                    <ModelResultCard name="XGBoost" icon="⚡" metrics={nontrivialEval.xgboost} labels={["No Refactoring", "Refactoring"]} />
                    <ModelResultCard name="Logistic Regression" icon="📐" metrics={nontrivialEval.logistic_regression} labels={["No Refactoring", "Refactoring"]} />
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ==== COMPARISON TAB ==== */}
        {activeTab === "comparison" && (
          <div className="dml-section">
            <h3>📊 Trivial vs Non-Trivial Refactoring Comparison</h3>
            {!comparison ? (
              <div className="empty-state-card">
                <p>Both trivial and non-trivial models must be trained to view the comparison.</p>
              </div>
            ) : (
              <>
                {/* Dataset Sizes */}
                <div className="comparison-datasets">
                  <div className="comp-dataset">
                    <h4>OnlyTrivial_dt.csv</h4>
                    <div className="comp-stats">
                      <span>Total: {comparison.datasets?.trivial?.total_samples?.toLocaleString()}</span>
                      <span>Train: {comparison.datasets?.trivial?.train_samples?.toLocaleString()}</span>
                      <span>Test: {comparison.datasets?.trivial?.test_samples?.toLocaleString()}</span>
                      <span>Champion: {comparison.datasets?.trivial?.champion_model}</span>
                      <span>F1: {comparison.datasets?.trivial?.champion_f1?.toFixed(4)}</span>
                    </div>
                  </div>
                  <div className="comp-dataset">
                    <h4>OnlyNonTrivial_dt.csv</h4>
                    <div className="comp-stats">
                      <span>Total: {comparison.datasets?.nontrivial?.total_samples?.toLocaleString()}</span>
                      <span>Train: {comparison.datasets?.nontrivial?.train_samples?.toLocaleString()}</span>
                      <span>Test: {comparison.datasets?.nontrivial?.test_samples?.toLocaleString()}</span>
                      <span>Champion: {comparison.datasets?.nontrivial?.champion_model}</span>
                      <span>F1: {comparison.datasets?.nontrivial?.champion_f1?.toFixed(4)}</span>
                    </div>
                  </div>
                </div>

                {/* Per-Model Comparison Table */}
                <table className="comparison-table">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th colSpan="2">Trivial</th>
                      <th colSpan="2">Non-Trivial</th>
                      <th>F1 Diff</th>
                    </tr>
                    <tr className="sub-header">
                      <th></th>
                      <th>F1</th><th>AUC</th>
                      <th>F1</th><th>AUC</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(comparison.model_comparison || {}).map(([model, data]) => (
                      <tr key={model}>
                        <td className="model-name-cell">{MODEL_ICONS[model] || ""} {model.replace(/_/g, " ")}</td>
                        <td>{data.trivial?.f1?.toFixed(4)}</td>
                        <td>{data.trivial?.roc_auc?.toFixed(4)}</td>
                        <td>{data.nontrivial?.f1?.toFixed(4)}</td>
                        <td>{data.nontrivial?.roc_auc?.toFixed(4)}</td>
                        <td className={data.f1_difference > 0 ? "positive" : data.f1_difference < 0 ? "negative" : ""}>
                          {data.f1_difference > 0 ? "+" : ""}{data.f1_difference?.toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Feature Importance Comparison */}
                <div className="fi-comparison">
                  {Object.entries(comparison.feature_importance_comparison || {}).map(([ds, data]) => (
                    <div key={ds} className="fi-comp-block">
                      <h4>{ds === "trivial" ? "Trivial" : "Non-Trivial"} Top Features ({data.champion_model})</h4>
                      <FeatureImportanceChart importances={data.top_5_features} maxBars={5} />
                    </div>
                  ))}
                </div>

                {/* Overlap Analysis */}
                {comparison.overlap_analysis && (
                  <div className="overlap-card">
                    <h4>🔗 Dataset Overlap Analysis</h4>
                    <p>Overlapping files: <strong>{comparison.overlap_analysis.overlapping_files}</strong></p>
                    <p>Overlapping classes: <strong>{comparison.overlap_analysis.overlapping_classes?.toLocaleString()}</strong></p>
                    <p className="subtle">{comparison.overlap_analysis.note}</p>
                  </div>
                )}

                {/* Limitations */}
                {comparison.limitations && (
                  <div className="limitations-card">
                    <h4>⚠ Limitations & Caveats</h4>
                    <ul>
                      {comparison.limitations.map((l, i) => <li key={i}>{l}</li>)}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ==== LIVE PREDICTION TAB ==== */}
        {activeTab === "predict" && (
          <div className="dml-section">
            <h3>🎯 Live Defect Risk Prediction</h3>
            {!defectEval || defectEval.status === "not_trained" ? (
              <div className="empty-state-card">
                <p>Train the defect classifier first to enable live predictions.</p>
              </div>
            ) : (
              <div className="predict-panel">
                <p className="predict-note">
                  Enter normalized metric values (0.0 – 1.0) for a software component.
                  The dataset uses pre-normalized Halstead/McCabe metrics.
                </p>
                <div className="predict-inputs">
                  {Object.entries(defectInput).map(([key, val]) => (
                    <div key={key} className="predict-input-group">
                      <label>{key}</label>
                      <input
                        type="number"
                        min="0" max="1" step="0.01"
                        value={val}
                        onChange={e => setDefectInput(prev => ({ ...prev, [key]: parseFloat(e.target.value) || 0 }))}
                      />
                    </div>
                  ))}
                </div>
                <button
                  className="btn-predict"
                  onClick={handleDefectPredict}
                  disabled={predicting}
                >
                  {predicting ? "⏳ Predicting..." : "🔮 Predict Defect Risk"}
                </button>

                {defectResult && !defectResult.error && (
                  <div className="prediction-result">
                    <div className="pr-header">
                      <span
                        className="pr-risk-badge"
                        style={{ background: RISK_COLORS[defectResult.risk_category] || "#636e72" }}
                      >
                        {defectResult.risk_category}
                      </span>
                      <span className="pr-label">{defectResult.prediction_label}</span>
                      <span className="pr-prob">Probability: {(defectResult.defect_probability * 100).toFixed(1)}%</span>
                      <span className="pr-model">Model: {defectResult.model_used}</span>
                    </div>
                    {defectResult.is_anomaly && (
                      <div className="pr-anomaly">⚠ Anomalous metric pattern detected (score: {defectResult.anomaly_score})</div>
                    )}
                    <div className="pr-evidence">
                      <h5>Evidence:</h5>
                      <ul>
                        {defectResult.evidence?.map((e, i) => <li key={i}>{e}</li>)}
                      </ul>
                    </div>
                    <FeatureImportanceChart importances={defectResult.top_contributing_factors} maxBars={5} />
                  </div>
                )}
                {defectResult?.error && (
                  <div className="prediction-error">{defectResult.error}</div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ==== PROCESS & DEVOPS TAB ==== */}
        {activeTab === "process_devops" && (
          <div className="dml-section">
            <h3>⚙ Process & DevOps Data Availability</h3>

            <div className="data-status-cards">
              {/* Process */}
              <div className="data-status-card">
                <h4>📋 Process Intelligence</h4>
                <div className="ds-metrics">
                  <span>Sprint Velocity Forecast</span>
                  <span>Cycle Time Forecast</span>
                  <span>Sprint Delay Risk</span>
                  <span>Sprint Predictability</span>
                  <span>WIP Monitoring</span>
                  <span>Story Spillover Rate</span>
                </div>
                {processStatus && (
                  <div className={`ds-status ${processStatus.sufficient_for_training ? "ready" : "insufficient"}`}>
                    <p>{processStatus.message}</p>
                    <p className="subtle">Historical records: {processStatus.historical_records}</p>
                    <p className="subtle">CSV datasets applicable: {processStatus.csv_datasets_applicable ? "Yes" : "No — code quality/refactoring datasets are not process data"}</p>
                  </div>
                )}
              </div>

              {/* DevOps */}
              <div className="data-status-card">
                <h4>🚀 DevOps Intelligence</h4>
                <div className="ds-metrics">
                  <span>Deployment Failure Probability</span>
                  <span>Deployment Success Rate</span>
                  <span>Mean Time to Recovery</span>
                  <span>Deployment Lead Time</span>
                  <span>Rollback Rate</span>
                  <span>Deployment Anomaly Detection</span>
                </div>
                {devopsStatus && (
                  <div className={`ds-status ${devopsStatus.sufficient_for_training ? "ready" : "insufficient"}`}>
                    <p>{devopsStatus.message}</p>
                    <p className="subtle">Historical records: {devopsStatus.historical_records}</p>
                    <p className="subtle">CSV datasets applicable: {devopsStatus.csv_datasets_applicable ? "Yes" : "No — code quality/refactoring datasets are not deployment data"}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
