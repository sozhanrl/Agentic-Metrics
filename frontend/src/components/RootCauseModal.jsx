import React, { useState, useEffect } from "react";
import { api } from "../api";

export default function RootCauseModal({ projectId, metricKey, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!projectId || !metricKey) return;
    setLoading(true);
    setError(null);
    api.getRootCause(projectId, metricKey)
      .then((res) => setData(res))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId, metricKey]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content wide root-cause-modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div className="modal-title-container">
            <h3 className="modal-title">🔬 Root Cause Diagnostic Trace</h3>
            <span className="modal-subtitle">
              Multi-hop backward causal graph traversal from symptom to root cause
            </span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            &times;
          </button>
        </header>

        {loading && (
          <div className="modal-loading-state">
            <div className="spinner" />
            <p>Traversing causal graph edges & historical correlations…</p>
          </div>
        )}

        {error && <div className="error-banner">{error}</div>}

        {data && (
          <div className="root-cause-body">
            {/* Top diagnostic summary */}
            <div className="rc-summary-banner">
              <div className="rc-summary-header">
                <span className="rc-icon">🎯</span>
                <div>
                  <h4 className="rc-summary-title">Diagnostic Finding</h4>
                  <p className="rc-summary-text">{data.summary}</p>
                </div>
              </div>
            </div>

            {/* Vertical Flow Causal Chain */}
            <div className="causal-chain-container">
              <h4 className="chain-heading">Causal Dependency Flow (Top = Symptom → Bottom = Root Origin)</h4>

              <div className="causal-chain-nodes">
                {data.causal_chain.map((node, index) => (
                  <React.Fragment key={node.metric_key}>
                    <div className={`causal-node-card ${node.is_root_cause ? "root-origin" : index === 0 ? "symptom-node" : "intermediate-node"}`}>
                      <div className="node-top-row">
                        <span className={`node-type-badge ${node.is_root_cause ? "root" : index === 0 ? "symptom" : "intermediate"}`}>
                          {node.is_root_cause ? "🔥 ROOT CAUSE" : index === 0 ? "⚠️ SYMPTOM" : "🔗 CONTRIBUTING FACTOR"}
                        </span>
                        <span className="node-conf">Conf: {(node.confidence * 100).toFixed(0)}%</span>
                      </div>

                      <div className="node-main-info">
                        <h5 className="node-name">{node.display_name}</h5>
                        <div className="node-value-badge">
                          {node.current_value} {node.unit}
                          <span className={`node-dev ${node.deviation_pct > 0 ? "bad" : "good"}`}>
                            ({node.deviation_pct > 0 ? "+" : ""}{node.deviation_pct}%)
                          </span>
                        </div>
                      </div>

                      <div className="node-meta-footer">
                        <span>Category: {node.category}</span>
                        <span>Evidence: {node.evidence_type}</span>
                        <span>Strength: {node.edge_strength}</span>
                      </div>
                    </div>

                    {index < data.causal_chain.length - 1 && (
                      <div className="causal-arrow-step">
                        <div className="arrow-line" />
                        <span className="arrow-label">
                          caused by ({data.causal_chain[index + 1].relation_to_parent || "direct"})
                        </span>
                        <div className="arrow-line" />
                      </div>
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>

            {/* Diagnostic Details Grid */}
            <div className="rc-details-grid">
              <div className="rc-detail-box">
                <span className="rc-detail-label">🛡️ Recommended Intervention</span>
                <p className="rc-detail-val">{data.recommended_intervention}</p>
              </div>
              <div className="rc-detail-box">
                <span className="rc-detail-label">💥 System Blast Radius</span>
                <p className="rc-detail-val">{data.system_impact}</p>
              </div>
              <div className="rc-detail-box full">
                <span className="rc-detail-label">📊 Evidence Ledger</span>
                <p className="rc-detail-val">{data.evidence_summary}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
