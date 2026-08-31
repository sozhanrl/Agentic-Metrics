import React, { useState } from "react";
import { api } from "../api";

export default function ConstraintsPanel({ projectId, onOptimized, onClose }) {
  const [riskBudget, setRiskBudget] = useState(0.5);
  const [costLimit, setCostLimit] = useState(15.0);
  const [timeLimit, setTimeLimit] = useState(10.0);
  const [optimizing, setOptimizing] = useState(false);
  const [results, setResults] = useState(null);

  const handleOptimize = async () => {
    setOptimizing(true);
    try {
      const constraints = [
        { constraint_type: "risk_budget", constraint_value: parseFloat(riskBudget) },
        { constraint_type: "cost_limit", constraint_value: parseFloat(costLimit) },
        { constraint_type: "time_limit", constraint_value: parseFloat(timeLimit) },
      ];
      const res = await api.optimizeRecommendations(projectId, constraints);
      setResults(res.optimized_recommendations);
      if (onOptimized) onOptimized(res.optimized_recommendations);
    } catch (err) {
      console.error(err);
    } finally {
      setOptimizing(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content constraints-modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div className="modal-title-container">
            <h3 className="modal-title">🎯 Goal-Constrained Optimizer</h3>
            <span className="modal-subtitle">
              Filter and rerank recommendations to satisfy risk budget, story point cost, and delivery deadlines
            </span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            &times;
          </button>
        </header>

        <div className="constraints-body">
          <div className="constraints-inputs-grid">
            <div className="constraint-field">
              <label>Max Risk Budget (0.1 - 1.0)</label>
              <input
                type="number"
                step="0.05"
                min="0.05"
                max="1.0"
                value={riskBudget}
                onChange={(e) => setRiskBudget(e.target.value)}
              />
              <span className="field-hint">Max allowable posterior variance risk</span>
            </div>

            <div className="constraint-field">
              <label>Cost Limit (Story Points)</label>
              <input
                type="number"
                step="1"
                min="1"
                max="50"
                value={costLimit}
                onChange={(e) => setCostLimit(e.target.value)}
              />
              <span className="field-hint">Max sprint capacity points to allocate</span>
            </div>

            <div className="constraint-field">
              <label>Time Limit (Days)</label>
              <input
                type="number"
                step="1"
                min="1"
                max="30"
                value={timeLimit}
                onChange={(e) => setTimeLimit(e.target.value)}
              />
              <span className="field-hint">Max acceptable remediation lead time</span>
            </div>
          </div>

          <button
            className="btn primary full-width"
            onClick={handleOptimize}
            disabled={optimizing}
          >
            {optimizing ? "Reranking Recommendations…" : "⚡ Optimize Recommendations"}
          </button>

          {results && (
            <div className="optimized-results-list">
              <h4>Optimized Recommendation Ranking ({results.length} items)</h4>
              {results.map((r, i) => (
                <div key={i} className="optimized-rec-item">
                  <div className="opt-title-row">
                    <span className="opt-rank">#{i + 1}</span>
                    <span className="opt-title">{r.title}</span>
                    <span className="opt-status">{r.constraint_status}</span>
                  </div>
                  <div className="opt-meta-row">
                    <span>Base Score: {r.priority_score} → <strong>Adjusted: {r.adjusted_score}</strong></span>
                    <span>Cost: {r.cost_estimate} pts</span>
                    <span>Time: {r.time_estimate}d</span>
                    <span>Risk: {r.risk_impact}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
