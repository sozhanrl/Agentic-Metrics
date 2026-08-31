import React from "react";

export default function HealthHero({ health, onOpenWhatIf, onOpenRisks }) {
  if (!health) return null;

  const score = health.overall_score || 0;
  const trend = health.status_trend || "stable";
  const pctChange = health.percentage_change;

  // Determine score color
  let scoreColor = "var(--teal)";
  let scoreClass = "healthy";
  if (score < 60) {
    scoreColor = "var(--rose)";
    scoreClass = "critical";
  } else if (score < 80) {
    scoreColor = "var(--amber)";
    scoreClass = "warning";
  }

  // Circular gauge calculations
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <section className="health-hero-card">
      <div className="health-hero-left">
        <div className="health-gauge-container">
          <svg className="health-gauge-svg" width="130" height="130" viewBox="0 0 130 130">
            <circle
              className="gauge-bg"
              cx="65"
              cy="65"
              r={radius}
              strokeWidth="10"
              fill="none"
            />
            <circle
              className="gauge-fill"
              cx="65"
              cy="65"
              r={radius}
              strokeWidth="10"
              fill="none"
              stroke={scoreColor}
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              transform="rotate(-90 65 65)"
            />
          </svg>
          <div className="gauge-text-center">
            <span className="gauge-number">{score.toFixed(0)}</span>
            <span className="gauge-label">HEALTH</span>
          </div>
        </div>

        <div className="health-status-info">
          <div className="health-title-row">
            <h2 className="health-title">Engineering Health Index</h2>
            <span className={`trend-badge ${trend}`}>
              {trend === "improving" ? "▲ Improving" : trend === "declining" ? "▼ Declining" : "● Stable"}
              {pctChange !== null && pctChange !== undefined && (
                <span className="pct-change"> ({pctChange > 0 ? "+" : ""}{pctChange}%)</span>
              )}
            </span>
          </div>
          <p className="health-summary">
            {health.key_drivers?.[0] || "Calculated in real-time from active telemetry & AI arbitration."}
          </p>
          <div className="health-quick-actions">
            <button className="btn-sm btn-ghost" onClick={onOpenWhatIf}>
              🎛️ What-If Simulator
            </button>
            <button className="btn-sm btn-ghost" onClick={onOpenRisks}>
              ⚠️ View Risks ({health.ai_risk_score?.toFixed(0) || 0} Risk Idx)
            </button>
          </div>
        </div>
      </div>

      <div className="health-subscores-grid">
        <div className="subscore-card">
          <div className="subscore-header">
            <span className="subscore-icon">💻</span>
            <span className="subscore-name">Code Quality</span>
          </div>
          <div className="subscore-val-row">
            <span className="subscore-val">{health.code_quality_score?.toFixed(0) || "--"}</span>
            <span className="subscore-max">/100</span>
          </div>
          <div className="subscore-bar">
            <div
              className="subscore-bar-fill cq"
              style={{ width: `${health.code_quality_score || 0}%` }}
            />
          </div>
        </div>

        <div className="subscore-card">
          <div className="subscore-header">
            <span className="subscore-icon">🔄</span>
            <span className="subscore-name">Process</span>
          </div>
          <div className="subscore-val-row">
            <span className="subscore-val">{health.process_score?.toFixed(0) || "--"}</span>
            <span className="subscore-max">/100</span>
          </div>
          <div className="subscore-bar">
            <div
              className="subscore-bar-fill proc"
              style={{ width: `${health.process_score || 0}%` }}
            />
          </div>
        </div>

        <div className="subscore-card">
          <div className="subscore-header">
            <span className="subscore-icon">🚀</span>
            <span className="subscore-name">DevOps</span>
          </div>
          <div className="subscore-val-row">
            <span className="subscore-val">{health.devops_score?.toFixed(0) || "--"}</span>
            <span className="subscore-max">/100</span>
          </div>
          <div className="subscore-bar">
            <div
              className="subscore-bar-fill do"
              style={{ width: `${health.devops_score || 0}%` }}
            />
          </div>
        </div>

        <div className="subscore-card risk-card">
          <div className="subscore-header">
            <span className="subscore-icon">🛡️</span>
            <span className="subscore-name">AI Risk Score</span>
          </div>
          <div className="subscore-val-row">
            <span className="subscore-val risk">{health.ai_risk_score?.toFixed(0) || "--"}</span>
            <span className="subscore-max">/100</span>
          </div>
          <div className="subscore-bar">
            <div
              className="subscore-bar-fill risk"
              style={{ width: `${health.ai_risk_score || 0}%` }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
