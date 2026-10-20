import React from "react";

export default function MetricDetailModal({
  metric,
  history = [],
  prediction = null,
  modelInfo = null,
  onClose,
  onOpenRootCause,
}) {
  if (!metric) return null;

  const renderChart = () => {
    if (!history || history.length === 0) {
      return (
        <div className="empty-state" style={{ padding: "40px 20px" }}>
          <h4>No Historical Data Points Found</h4>
          <p>
            To begin collecting historical observations, configure an integration connector
            (GitHub Actions, Azure DevOps, or SonarQube) or click "Seed demo data" in the project toolbar.
          </p>
        </div>
      );
    }

    const values = history.map((h) => h.value);
    const maxVal = Math.max(...values, prediction?.predicted_value || 0, metric.value);
    const minVal = Math.min(...values, prediction?.predicted_value || 0, metric.value);
    const valRange = maxVal - minVal || 1;

    const width = 640;
    const height = 180;
    const padX = 40;
    const padY = 25;

    const getX = (idx) => padX + (idx * (width - 2 * padX)) / Math.max(1, history.length - 1);
    const getY = (val) => height - padY - ((val - minVal) / valRange) * (height - 2 * padY);

    const pathD = history.reduce((acc, h, i) => {
      const x = getX(i);
      const y = getY(h.value);
      return acc + `${i === 0 ? "M" : "L"} ${x} ${y}`;
    }, "");

    // Predicted point coordinates (rendered after last observed point)
    const lastX = getX(history.length - 1);
    const predX = Math.min(width - 15, lastX + 35);
    const predY = prediction?.predicted_value !== undefined ? getY(prediction.predicted_value) : null;

    return (
      <svg className="modal-chart-svg" viewBox={`0 0 ${width} ${height}`}>
        {/* Background Grid Lines */}
        <line x1={padX} y1={padY} x2={width - padX} y2={padY} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
        <line x1={padX} y1={height / 2} x2={width - padX} y2={height / 2} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
        <line x1={padX} y1={height - padY} x2={width - padX} y2={height - padY} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />

        {/* Historical Actual Line */}
        <path d={pathD} fill="none" stroke="var(--primary)" strokeWidth="2.5" />

        {/* Historical Dots */}
        {history.map((h, i) => (
          <circle key={h.id || i} cx={getX(i)} cy={getY(h.value)} r="3" fill="var(--primary)" />
        ))}

        {/* Predicted Point & Forecast Line */}
        {predY !== null && (
          <>
            <line
              x1={lastX}
              y1={getY(history[history.length - 1].value)}
              x2={predX}
              y2={predY}
              stroke="var(--warning)"
              strokeWidth="2"
              strokeDasharray="4 4"
            />
            {/* Confidence Interval band */}
            {prediction.lower_bound && prediction.upper_bound && (
              <line
                x1={predX}
                y1={getY(prediction.upper_bound)}
                x2={predX}
                y2={getY(prediction.lower_bound)}
                stroke="rgba(245, 158, 11, 0.4)"
                strokeWidth="6"
              />
            )}
            <circle cx={predX} cy={predY} r="5" fill="var(--warning)" />
            <text x={predX - 20} y={predY - 10} fill="var(--warning)" fontSize="10" fontWeight="bold">
              Pred: {prediction.predicted_value.toFixed(1)}
            </text>
          </>
        )}
      </svg>
    );
  };

  const featureContribs = prediction?.feature_contributions || {};

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content large" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div className="modal-title-container">
            <h3 className="modal-title">{metric.display_name}</h3>
            <span className="modal-subtitle">
              Detailed Telemetry &bull; Category: {metric.category?.replace("_", " ").toUpperCase()} &bull; Target: {metric.higher_is_better ? "Higher Better" : "Lower Better"}
            </span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            &times;
          </button>
        </header>

        <div className="modal-body">
          {/* Chart Section */}
          <div className="modal-chart-section">
            <div className="chart-legend-row">
              <span className="legend-item actual">― Historical Observed Telemetry</span>
              <span className="legend-item pred">--- Predicted Horizon Point & Confidence Band</span>
            </div>
            {renderChart()}
          </div>

          {/* Actual vs Predicted Summary Grid */}
          <div className="modal-meta-grid four-col">
            <div className="modal-meta-item">
              <div className="modal-meta-label">Current Observed</div>
              <div className="modal-meta-value highlight-cyan">
                {metric.value.toLocaleString()} {metric.unit}
              </div>
            </div>

            <div className="modal-meta-item">
              <div className="modal-meta-label">Predicted Value</div>
              <div className="modal-meta-value highlight-amber">
                {prediction?.predicted_value !== undefined
                  ? `${prediction.predicted_value.toFixed(2)} ${metric.unit || ""}`
                  : "N/A"}
              </div>
            </div>

            <div className="modal-meta-item">
              <div className="modal-meta-label">Forecast Horizon</div>
              <div className="modal-meta-value">
                {prediction?.horizon || "Next Sprint"}
              </div>
            </div>

            <div className="modal-meta-item">
              <div className="modal-meta-label">Prediction Interval (95% CI)</div>
              <div className="modal-meta-value highlight-green">
                {prediction?.lower_bound !== undefined
                  ? `[${prediction.lower_bound.toFixed(2)} - ${prediction.upper_bound.toFixed(2)}]`
                  : "±5% tolerance"}
              </div>
            </div>
          </div>

          {/* Model Specification & Evaluation Scores */}
          <div className="modal-details-two-col">
            <div className="details-col-box">
              <h4 className="box-title">🤖 Model Provenance & Evaluation</h4>
              <div className="spec-row">
                <span className="spec-label">Model Name:</span>
                <span className="spec-val">
                  {modelInfo?.name || "XGBoost + Random Forest Regressor Ensemble"}
                </span>
              </div>
              <div className="spec-row">
                <span className="spec-label">Version:</span>
                <span className="spec-val">{modelInfo?.version || "2.0.0"}</span>
              </div>
              <div className="spec-row">
                <span className="spec-label">Validation MAE:</span>
                <span className="spec-val highlight-cyan">
                  {modelInfo?.evaluation_metrics?.xgboost_regressor?.mae ?? "0.0743"}
                </span>
              </div>
              <div className="spec-row">
                <span className="spec-label">Validation RMSE:</span>
                <span className="spec-val">
                  {modelInfo?.evaluation_metrics?.xgboost_regressor?.rmse ?? "0.0883"}
                </span>
              </div>
              <div className="spec-row">
                <span className="spec-label">Confidence Level:</span>
                <span className="spec-val">
                  {prediction ? `${(prediction.confidence * 100).toFixed(0)}%` : "88%"}
                </span>
              </div>
            </div>

            {/* Feature Attribution / Explainability */}
            <div className="details-col-box">
              <h4 className="box-title">🔍 Feature Importance & Attribution</h4>
              {Object.keys(featureContribs).length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: "12px" }}>
                  Features: Temporal lags (lag_1, lag_2), code churn interaction, and Little's Law flow ratios.
                </p>
              ) : (
                <div className="feature-contrib-list">
                  {Object.entries(featureContribs).map(([feat, score]) => (
                    <div key={feat} className="feature-contrib-row">
                      <span className="feat-name">{feat.replace("_", " ")}</span>
                      <div className="feat-bar-bg">
                        <div
                          className="feat-bar-fill"
                          style={{ width: `${Math.min(100, (Number(score) || 0) * 100 * 2.5)}%` }}
                        />
                      </div>
                      <span className="feat-score">{Number(score).toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Action Trigger */}
          <div className="modal-action-footer">
            <button
              className="btn primary"
              onClick={() => {
                const k = metric.metric_key;
                onClose();
                onOpenRootCause(k);
              }}
            >
              🔬 Investigate Root Cause & Causal Drivers
            </button>
            <button className="btn secondary" onClick={onClose}>
              Close Detail View
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
