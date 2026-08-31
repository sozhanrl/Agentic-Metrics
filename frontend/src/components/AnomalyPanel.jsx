import React, { useState } from "react";
import { api } from "../api";

export default function AnomalyPanel({ anomalies = [], onAcknowledge, onInvestigateRootCause }) {
  const [loadingId, setLoadingId] = useState(null);

  const handleAck = async (id) => {
    setLoadingId(id);
    try {
      await api.acknowledgeAnomaly(id);
      if (onAcknowledge) onAcknowledge(id);
    } catch (err) {
      console.error("Failed to acknowledge anomaly", err);
    } finally {
      setLoadingId(null);
    }
  };

  if (!anomalies || anomalies.length === 0) {
    return (
      <div className="anomaly-panel clean">
        <div className="anomaly-clean-state">
          <span className="clean-icon">✨</span>
          <div>
            <div className="clean-title">No Statistical Anomalies Detected</div>
            <div className="clean-sub">All monitored metrics are operating within 2σ normal historical distribution.</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <section className="anomaly-section">
      <div className="section-heading">
        <div className="heading-left">
          <span className="section-icon">⚡</span>
          <div>
            <h2>AI Anomaly Detection ({anomalies.length})</h2>
            <span className="section-caption">Statistical deviations detected beyond expected operating boundaries</span>
          </div>
        </div>
      </div>

      <div className="anomaly-cards-grid">
        {anomalies.map((a) => (
          <div key={a.id || a.metric_key} className={`anomaly-card severity-${a.severity} ${a.is_acknowledged ? "acknowledged" : ""}`}>
            <div className="anomaly-card-top">
              <div className="anomaly-metric-header">
                <span className={`severity-badge ${a.severity}`}>{a.severity.toUpperCase()}</span>
                <h3 className="anomaly-metric-name">{a.metric_name}</h3>
              </div>
              <div className="anomaly-deviation">
                <span className="deviation-val">{a.deviation_pct > 0 ? "+" : ""}{a.deviation_pct}%</span>
                <span className="deviation-label">deviation</span>
              </div>
            </div>

            <div className="anomaly-stats-row">
              <div className="stat-pill">
                <span className="stat-pill-label">Observed:</span>
                <span className="stat-pill-val">{a.current_value}</span>
              </div>
              <div className="stat-pill">
                <span className="stat-pill-label">Expected Range:</span>
                <span className="stat-pill-val">{a.expected_min} – {a.expected_max}</span>
              </div>
            </div>

            {a.possible_cause && (
              <div className="anomaly-detail-box cause">
                <span className="box-label">🔍 Possible Cause:</span>
                <p className="box-text">{a.possible_cause}</p>
              </div>
            )}

            {a.recommended_action && (
              <div className="anomaly-detail-box action">
                <span className="box-label">💡 Recommended Action:</span>
                <p className="box-text">{a.recommended_action}</p>
              </div>
            )}

            <div className="anomaly-actions-row">
              <button
                className="btn-sm btn-outline"
                onClick={() => onInvestigateRootCause && onInvestigateRootCause(a.metric_key)}
              >
                🔬 Root Cause Trace
              </button>
              {!a.is_acknowledged && (
                <button
                  className="btn-sm btn-ghost"
                  onClick={() => handleAck(a.id)}
                  disabled={loadingId === a.id}
                >
                  {loadingId === a.id ? "Acknowledging…" : "✓ Acknowledge"}
                </button>
              )}
              {a.is_acknowledged && (
                <span className="acknowledged-tag">✓ Acknowledged</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
