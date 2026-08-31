import React, { useState, useEffect } from "react";
import { api } from "../api";

export default function CausalGraphVisualizer({ projectId, metrics = [], recommendations = [] }) {
  const [graphData, setGraphData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [evolving, setEvolving] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState(null);

  const loadGraph = async () => {
    setLoading(true);
    try {
      const data = await api.getCausalGraph(projectId);
      setGraphData(data || []);
    } catch (err) {
      console.error("Failed to load causal graph", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) loadGraph();
  }, [projectId]);

  const handleEvolve = async () => {
    setEvolving(true);
    try {
      await api.evolveCausalGraph(projectId);
      await loadGraph();
    } catch (err) {
      console.error(err);
    } finally {
      setEvolving(false);
    }
  };

  // Metric Inspector node details computation
  const getMetricDetails = (metricKey) => {
    const metricObj = metrics.find((m) => m.metric_key === metricKey);
    const upstreamEdges = graphData.filter((e) => e.target_metric === metricKey);
    const downstreamEdges = graphData.filter((e) => e.source_metric === metricKey);
    const relatedRecs = recommendations.filter((r) =>
      r.title.toLowerCase().includes(metricKey.replace(/_/g, " ")) ||
      (r.related_metrics && metricObj && r.related_metrics.includes(metricObj.id))
    );

    return {
      metricKey,
      name: metricObj?.display_name || metricKey.replace(/_/g, " ").toUpperCase(),
      currentValue: metricObj ? `${metricObj.value} ${metricObj.unit}` : "Recorded in telemetry",
      target: metricObj?.target_value || "Nominal Band",
      upstreamCauses: upstreamEdges,
      downstreamEffects: downstreamEdges,
      relatedRecommendations: relatedRecs,
    };
  };

  return (
    <div className="causal-graph-view">
      <div className="causal-header">
        <div>
          <h2>Self-Evolving Causal Knowledge Explorer</h2>
          <p className="causal-subtitle">
            Click any causal edge or metric node to inspect upstream causes, downstream blast radius, relationship strength, and evidence.
          </p>
        </div>
        <button className="btn primary" onClick={handleEvolve} disabled={evolving}>
          {evolving ? "Evolving Knowledge Graph…" : "🧬 Evolve Causal Graph"}
        </button>
      </div>

      {loading && (
        <div className="section-loading">
          <div className="spinner" />
          <p>Loading causal dependency topology…</p>
        </div>
      )}

      {!loading && graphData.length === 0 && (
        <div className="empty-state">
          <p>No causal edges recorded yet. Run the agent pipeline to discover causal relationships.</p>
        </div>
      )}

      <div className="causal-edges-grid">
        {graphData.map((edge) => (
          <div
            key={edge.id || `${edge.source_metric}-${edge.target_metric}`}
            className={`edge-card ${edge.is_active ? "active" : "retired"}`}
            onClick={() => setSelectedMetric(edge.source_metric)}
            title="Click to explore node dependencies"
          >
            <div className="edge-top">
              <span className={`edge-type-pill ${edge.effect_type}`}>
                {edge.effect_type?.toUpperCase() || "DIRECT"}
              </span>
              <span className={`edge-evidence-pill ${edge.evidence_type}`}>
                {edge.evidence_type?.toUpperCase()}
              </span>
            </div>

            <div className="edge-path">
              <span className="source-node">{edge.source_metric}</span>
              <span className="edge-arrow">──▶</span>
              <span className="target-node">{edge.target_metric}</span>
            </div>

            <div className="edge-metrics-row">
              <div className="edge-stat">
                <span className="stat-label">Strength:</span>
                <span className="stat-val">{(edge.edge_strength * 100).toFixed(0)}%</span>
              </div>
              <div className="edge-stat">
                <span className="stat-label">Confidence:</span>
                <span className="stat-val">{(edge.causal_confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="edge-stat">
                <span className="stat-label">Confirmations:</span>
                <span className="stat-val">{edge.confirmations || 0}</span>
              </div>
              <div className="edge-stat">
                <span className="stat-label">Refutations:</span>
                <span className="stat-val">{edge.refutations || 0}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Metric Inspector Modal */}
      {selectedMetric && (() => {
        const details = getMetricDetails(selectedMetric);
        return (
          <div className="modal-backdrop" onClick={() => setSelectedMetric(null)}>
            <div className="modal-content metric-inspector-modal" onClick={(e) => e.stopPropagation()}>
              <header className="modal-header">
                <div>
                  <h3 className="modal-title">🔬 Causal Node Inspector: {details.name}</h3>
                  <span className="modal-subtitle">Upstream drivers & downstream system blast radius</span>
                </div>
                <button className="modal-close-btn" onClick={() => setSelectedMetric(null)}>
                  &times;
                </button>
              </header>

              <div className="inspector-body">
                <div className="inspector-stats-strip">
                  <div className="inspector-stat">
                    <span className="lbl">Current Telemetry:</span>
                    <span className="val">{details.currentValue}</span>
                  </div>
                  <div className="inspector-stat">
                    <span className="lbl">Target Band:</span>
                    <span className="val">{details.target}</span>
                  </div>
                </div>

                <div className="inspector-causal-section">
                  <h4>⬆️ Upstream Causes (Drivers)</h4>
                  {details.upstreamCauses.length === 0 ? (
                    <p className="empty-sub">No upstream cause drivers registered.</p>
                  ) : (
                    <ul className="inspector-list">
                      {details.upstreamCauses.map((e, i) => (
                        <li key={i}>
                          <strong>{e.source_metric}</strong> &bull; Strength: {(e.edge_strength * 100).toFixed(0)}% ({e.evidence_type})
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="inspector-causal-section">
                  <h4>⬇️ Downstream Effects (Blast Radius)</h4>
                  {details.downstreamEffects.length === 0 ? (
                    <p className="empty-sub">No downstream dependencies registered.</p>
                  ) : (
                    <ul className="inspector-list">
                      {details.downstreamEffects.map((e, i) => (
                        <li key={i}>
                          <strong>{e.target_metric}</strong> &bull; Strength: {(e.edge_strength * 100).toFixed(0)}% ({e.evidence_type})
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {details.relatedRecommendations.length > 0 && (
                  <div className="inspector-causal-section">
                    <h4>🎯 Related Prioritized Recommendations</h4>
                    <ul className="inspector-list">
                      {details.relatedRecommendations.map((r) => (
                        <li key={r.id}>
                          <strong>{r.title}</strong> (Priority: {r.priority_score?.toFixed(0)})
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
