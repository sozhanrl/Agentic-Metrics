import React, { useState, useEffect } from "react";
import { api } from "../api";

export default function RiskPredictor({ projectId }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    api.getProjectRisks(projectId)
      .then((res) => setReport(res))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="section-loading">
        <div className="spinner" />
        <p>Evaluating forward-looking predictive risk models…</p>
      </div>
    );
  }

  if (error) return <div className="error-banner">{error}</div>;
  if (!report) return null;

  return (
    <div className="risks-view-container">
      <div className="risks-hero-header">
        <div className="risks-hero-left">
          <span className="risks-icon">🛡️</span>
          <div>
            <h2>Predictive Risk Intelligence</h2>
            <p className="risks-subtitle">
              Forward-looking risk projections computed via time-series extrapolation and stability metrics.
            </p>
          </div>
        </div>
        <div className={`risk-level-badge level-${report.overall_risk_level}`}>
          System Risk: {report.overall_risk_level?.toUpperCase()}
        </div>
      </div>

      <div className="risks-grid">
        {report.risks.map((risk, i) => {
          const isUnknown = !risk.has_sufficient_data || risk.risk_level === "unknown";

          return (
            <div key={i} className={`risk-card ${isUnknown ? "insufficient-data" : `level-${risk.risk_level}`}`}>
              <div className="risk-card-top">
                <div className="risk-title-box">
                  <span className={`risk-badge ${isUnknown ? "unknown" : risk.risk_level}`}>
                    {isUnknown ? "INSUFFICIENT DATA" : `${risk.risk_level.toUpperCase()} RISK`}
                  </span>
                  <h3 className="risk-card-title">{risk.title}</h3>
                </div>

                {!isUnknown && (
                  <div className="risk-prob-gauge">
                    <span className="prob-val">{(risk.probability * 100).toFixed(0)}%</span>
                    <span className="prob-label">probability</span>
                  </div>
                )}
              </div>

              <div className="risk-body">
                <div className="risk-reason-box">
                  <span className="risk-box-label">🔍 Risk Diagnostics:</span>
                  <p className="risk-reason-text">{risk.reason}</p>
                </div>

                {!isUnknown && risk.recommended_mitigation && (
                  <div className="risk-mitigation-box">
                    <span className="risk-box-label">💡 Recommended Mitigation:</span>
                    <p className="risk-mitigation-text">{risk.recommended_mitigation}</p>
                  </div>
                )}

                <div className="risk-footer-meta">
                  <span>Metric: <strong>{risk.affected_metric}</strong></span>
                  <span>Confidence: <strong>{(risk.confidence * 100).toFixed(0)}%</strong></span>
                  <span>Samples: <strong>{risk.data_points_count} points</strong></span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
