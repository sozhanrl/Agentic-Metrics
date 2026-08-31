import React, { useState } from "react";
import { api } from "../api";

export default function WhatIfSimulator({ projectId, metrics = [], onClose }) {
  const [simulatedValues, setSimulatedValues] = useState(() => {
    const init = {};
    metrics.forEach((m) => {
      init[m.metric_key] = m.value;
    });
    return init;
  });

  const [result, setResult] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState(null);

  const handleSliderChange = (key, val) => {
    setSimulatedValues((prev) => ({
      ...prev,
      [key]: parseFloat(val),
    }));
  };

  const handleRunSimulation = async () => {
    setSimulating(true);
    setError(null);
    try {
      const res = await api.simulateWhatIf(projectId, simulatedValues);
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setSimulating(false);
    }
  };

  const handleReset = () => {
    const resetVals = {};
    metrics.forEach((m) => {
      resetVals[m.metric_key] = m.value;
    });
    setSimulatedValues(resetVals);
    setResult(null);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content wide what-if-modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div className="modal-title-container">
            <h3 className="modal-title">🎛️ What-If Simulation Sandbox</h3>
            <span className="modal-subtitle">
              Adjust metric values to project simulated health scores and priority shifts. (In-memory only — never modifies DB)
            </span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            &times;
          </button>
        </header>

        <div className="what-if-grid">
          {/* Controls Column */}
          <div className="what-if-controls">
            <div className="controls-header">
              <h4>Metric Parameter Inputs</h4>
              <button className="btn-link" onClick={handleReset}>
                Reset to Baseline
              </button>
            </div>

            <div className="sliders-list">
              {metrics.map((m) => {
                const cur = simulatedValues[m.metric_key] ?? m.value;
                const isModified = Math.abs(cur - m.value) > 0.01;

                return (
                  <div key={m.id} className={`slider-row ${isModified ? "modified" : ""}`}>
                    <div className="slider-label-row">
                      <span className="metric-slider-name">{m.display_name}</span>
                      <span className="metric-slider-val">
                        {cur} {m.unit}
                        {isModified && (
                          <span className="slider-delta">
                            ({cur > m.value ? "+" : ""}{(cur - m.value).toFixed(1)})
                          </span>
                        )}
                      </span>
                    </div>

                    <input
                      type="range"
                      className="metric-slider"
                      min={Math.max(0, m.value * 0.2)}
                      max={Math.max(100, m.value * 2.2)}
                      step={m.unit === "%" ? 1 : 0.5}
                      value={cur}
                      onChange={(e) => handleSliderChange(m.metric_key, e.target.value)}
                    />
                    <div className="slider-meta">
                      <span>Base: {m.value}{m.unit}</span>
                      <span>{m.higher_is_better ? "Higher better" : "Lower better"}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            <button
              className="btn primary full-width"
              onClick={handleRunSimulation}
              disabled={simulating}
            >
              {simulating ? "Projecting Trajectory…" : "⚡ Run What-If Simulation"}
            </button>
          </div>

          {/* Results Column */}
          <div className="what-if-results-panel">
            {error && <div className="error-banner">{error}</div>}

            {!result && !error && (
              <div className="simulation-placeholder">
                <span className="placeholder-icon">🔮</span>
                <p>Adjust the sliders on the left and click <strong>"Run What-If Simulation"</strong> to view real-time projected impact on project health and recommendation ranking.</p>
              </div>
            )}

            {result && (
              <div className="simulation-results-content">
                <div className="sim-badge-row">
                  <span className="simulated-pill">🧪 SIMULATED PREDICTION</span>
                  <span className="sim-gain-pill">
                    {result.health_delta >= 0 ? "+" : ""}{result.health_delta.toFixed(1)} Health Pts ({result.health_percentage_gain > 0 ? "+" : ""}{result.health_percentage_gain}%)
                  </span>
                </div>

                <div className="sim-comparison-cards">
                  <div className="sim-kpi-box">
                    <div className="sim-kpi-label">Health Score</div>
                    <div className="sim-kpi-val-row">
                      <span className="base-val">{result.baseline_health.toFixed(1)}</span>
                      <span className="arrow-sep">→</span>
                      <span className="pred-val">{result.predicted_health.toFixed(1)}</span>
                    </div>
                  </div>

                  <div className="sim-kpi-box">
                    <div className="sim-kpi-label">AI Risk Score</div>
                    <div className="sim-kpi-val-row">
                      <span className="base-val">{result.baseline_risk.toFixed(1)}</span>
                      <span className="arrow-sep">→</span>
                      <span className="pred-val risk">{result.predicted_risk.toFixed(1)}</span>
                    </div>
                  </div>
                </div>

                <div className="sim-notes-box">
                  <div className="notes-heading">Simulation Takeaways:</div>
                  <ul>
                    {result.simulation_notes.map((note, i) => (
                      <li key={i}>{note}</li>
                    ))}
                  </ul>
                </div>

                <div className="sim-reranked-section">
                  <h4>Projected Recommendation Priority Shifts</h4>
                  <div className="sim-diff-list">
                    {result.recommendation_diffs.map((d) => (
                      <div key={d.metric_key} className={`sim-diff-item ${d.status}`}>
                        <div className="diff-title-row">
                          <span className={`diff-status-pill ${d.status}`}>{d.status.toUpperCase()}</span>
                          <span className="diff-metric-name">{d.title}</span>
                        </div>
                        <div className="diff-scores-row">
                          <span>Priority: {d.baseline_priority} → {d.simulated_priority} ({d.priority_delta > 0 ? "+" : ""}{d.priority_delta})</span>
                          <span>Rank: #{d.rank_before} → #{d.rank_after}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
