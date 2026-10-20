import React from "react";

export default function MetricCard({ metric, history = [], prediction = null, onClick }) {
  // Compute change from previous observation if history has at least 2 points
  let changePct = null;
  if (history && history.length >= 2) {
    const prev = history[history.length - 2].value;
    const curr = metric.value;
    if (prev !== 0) {
      changePct = ((curr - prev) / Math.abs(prev)) * 100;
    }
  }

  // Derive risk badge
  let riskStatus = "nominal";
  if (prediction?.risk_level) {
    riskStatus = prediction.risk_level;
  } else if (metric.higher_is_better) {
    if (changePct !== null && changePct < -10) riskStatus = "warning";
  } else {
    if (changePct !== null && changePct > 10) riskStatus = "warning";
  }

  const renderSparkline = () => {
    if (!history || history.length <= 1) {
      return (
        <div
          className="sparkline-container"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-muted)",
            fontSize: "10px",
          }}
        >
          No history yet
        </div>
      );
    }
    const values = history.map((h) => h.value);
    const maxVal = Math.max(...values);
    const minVal = Math.min(...values);
    const valRange = maxVal - minVal || 1;

    const width = 120;
    const height = 30;
    const paddingX = 5;
    const paddingY = 5;

    const getX = (index) => paddingX + (index * (width - 2 * paddingX)) / (history.length - 1);
    const getY = (val) => height - paddingY - ((val - minVal) / valRange) * (height - 2 * paddingY);

    const pathD = history.reduce((acc, h, i) => {
      const x = getX(i);
      const y = getY(h.value);
      return acc + `${i === 0 ? "M" : "L"} ${x} ${y}`;
    }, "");

    const lastIndex = history.length - 1;
    const lastX = getX(lastIndex);
    const lastY = getY(history[lastIndex].value);

    return (
      <svg className="sparkline-container" viewBox={`0 0 ${width} ${height}`}>
        <path className="sparkline-glow" d={pathD} />
        <path className="sparkline-path" d={pathD} />
        <circle className="sparkline-dot" cx={lastX} cy={lastY} r="2.5" />
      </svg>
    );
  };

  return (
    <div className={`metric-card ${riskStatus}`} onClick={onClick} role="button" tabIndex={0}>
      <div className="metric-header-row">
        <div className="metric-name">{metric.display_name}</div>
        <span className={`metric-risk-pill ${riskStatus}`}>
          {riskStatus.toUpperCase()}
        </span>
      </div>

      {/* Observed Measurement */}
      <div className="metric-observation-section">
        <div className="metric-observation-label">Observed Telemetry</div>
        <div className="metric-value">
          {metric.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          <span className="metric-unit">{metric.unit}</span>
          {changePct !== null && (
            <span className={`metric-change-pill ${changePct >= 0 ? "positive" : "negative"}`}>
              {changePct >= 0 ? "↑" : "↓"} {Math.abs(changePct).toFixed(1)}%
            </span>
          )}
        </div>
      </div>

      {/* Predicted ML Forecast (Clearly distinguished) */}
      <div className="metric-prediction-box">
        <div className="metric-prediction-label">
          <span>🔮 ML Forecast</span>
          <span className="metric-horizon">({prediction?.horizon || "Next Cycle"})</span>
        </div>
        <div className="metric-predicted-val">
          {prediction?.predicted_value !== undefined
            ? `${prediction.predicted_value.toFixed(2)} ${metric.unit || ""}`
            : "Model Initialized"}
          {prediction?.lower_bound !== undefined && (
            <span className="metric-prediction-ci">
              [{prediction.lower_bound.toFixed(1)} - {prediction.upper_bound.toFixed(1)}]
            </span>
          )}
        </div>
      </div>

      {renderSparkline()}

      <div className="metric-meta-footer">
        <span className="metric-updated">
          Updated {new Date(metric.recorded_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })}
        </span>
        <span className="metric-status-badge">
          {prediction ? "✓ ML Projected" : "● Telemetry Ready"}
        </span>
      </div>
    </div>
  );
}
