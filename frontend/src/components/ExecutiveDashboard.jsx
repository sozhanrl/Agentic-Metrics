import React, { useState } from "react";
import SkeletonLoader from "./SkeletonLoader";
import ApiErrorState from "./ApiErrorState";
import AIDecisionReplayModal from "./AIDecisionReplayModal";

export default function ExecutiveDashboard({
  health,
  recommendations = [],
  anomalies = [],
  metrics = [],
  loading = false,
  error = null,
  onRetry,
  onOpenRootCause,
  onStartAction,
}) {
  const [selectedRecForReplay, setSelectedRecForReplay] = useState(null);

  if (loading) {
    return (
      <div className="executive-container">
        <SkeletonLoader type="hero" />
        <SkeletonLoader type="cards" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="executive-container">
        <ApiErrorState
          title="Unable to load Executive Intelligence"
          message="Could not retrieve project health and recommendation analytics."
          endpoint={error.endpoint}
          status={error.status}
          errorDetails={error.message}
          onRetry={onRetry}
        />
      </div>
    );
  }

  const hasData = metrics && metrics.length > 0;
  const overallScore = health?.overall_score ?? null;
  const trend = health?.status_trend || "stable";
  const pctChange = health?.percentage_change;

  const topRecs = (recommendations || []).slice(0, 3);

  // Derive evidence-grounded AI takeaways
  const aiTakeaways = [];
  if (health?.key_drivers && health.key_drivers.length > 0) {
    aiTakeaways.push(...health.key_drivers);
  }
  if (anomalies && anomalies.length > 0) {
    aiTakeaways.push(`⚡ ${anomalies.length} statistical metric anomalies currently flagged for triage.`);
  }
  if (topRecs.length > 0) {
    aiTakeaways.push(`🎯 Recommendation "${topRecs[0].title}" is currently the highest expected impact item.`);
  }
  if (aiTakeaways.length === 0) {
    if (!hasData) {
      aiTakeaways.push("Not enough historical observations to calculate AI takeaways. Ingest telemetry data to begin analysis.");
    } else {
      aiTakeaways.push("Telemetry baseline is operating nominally across monitored quality parameters.");
    }
  }

  return (
    <div className="executive-container">
      <div className="exec-header">
        <div>
          <h2>Executive Engineering Summary</h2>
          <span className="section-caption">Executive 30-second situational awareness overview</span>
        </div>
        {overallScore !== null ? (
          <div className="exec-health-pill">
            Health Index: <strong>{overallScore.toFixed(0)}/100</strong>{" "}
            <span className={`trend-badge ${trend}`}>
              {trend === "improving" ? "▲ Improving" : trend === "declining" ? "▼ Declining" : "● Stable"}
              {pctChange !== null && pctChange !== undefined && (
                <span> ({pctChange > 0 ? "+" : ""}{pctChange}%)</span>
              )}
            </span>
          </div>
        ) : (
          <div className="exec-health-pill insufficient">
            <span>Insufficient data</span>
          </div>
        )}
      </div>

      {/* Sub-scores 4-card strip */}
      <div className="exec-score-row">
        <div className="exec-score-item">
          <div className="score-lbl">Code Quality</div>
          <div className="score-num">
            {health?.code_quality_score !== undefined ? Math.round(health.code_quality_score) : "--"}
          </div>
        </div>

        <div className="exec-score-item">
          <div className="score-lbl">Process</div>
          <div className="score-num">
            {health?.process_score !== undefined ? Math.round(health.process_score) : "--"}
          </div>
        </div>

        <div className="exec-score-item">
          <div className="score-lbl">DevOps</div>
          <div className="score-num">
            {health?.devops_score !== undefined ? Math.round(health.devops_score) : "--"}
          </div>
        </div>

        <div className="exec-score-item risk">
          <div className="score-lbl">AI Risk Index</div>
          <div className="score-num risk">
            {health?.ai_risk_score !== undefined ? Math.round(health.ai_risk_score) : "--"}
          </div>
        </div>
      </div>

      <div className="exec-grid">
        {/* AI Key Takeaways Box */}
        <div className="exec-card ai-insights-card">
          <h3 className="exec-card-title">🤖 AI Key Takeaways</h3>
          <ul className="exec-takeaways-list">
            {aiTakeaways.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>

        {/* Project Vulnerabilities */}
        <div className="exec-card weaknesses-card">
          <h3 className="exec-card-title">⚠️ Key System Vulnerabilities</h3>
          <ul className="exec-list negative">
            {health?.top_weaknesses?.map((w, i) => (
              <li key={i}>! {w}</li>
            ))}
            {(!health?.top_weaknesses || health.top_weaknesses.length === 0) && (
              <li>No major vulnerabilities flagged in telemetry.</li>
            )}
          </ul>
        </div>

        {/* Top 3 Prioritized Action Items */}
        <div className="exec-card top-recs-card full-width">
          <h3 className="exec-card-title">🎯 Highest Priority Action Items (Top 3)</h3>
          {topRecs.length === 0 ? (
            <div className="empty-state-inline">
              <p>No active recommendations for this project.</p>
            </div>
          ) : (
            <div className="exec-recs-list">
              {topRecs.map((r, i) => {
                const plan = r.action_plan;
                const priority = r.priority_score ? Math.round(r.priority_score) : 0;
                const severity = priority >= 60 ? "Critical" : priority >= 30 ? "Attention" : "Watch";

                return (
                  <div key={r.id} className="exec-rec-card">
                    <div className="exec-rec-card-top">
                      <div className="exec-rec-rank-badge">#{i + 1}</div>
                      <div className="exec-rec-main-info">
                        <div className="exec-rec-badge-row">
                          <span className={`severity-tag ${severity.toLowerCase()}`}>
                            {severity.toUpperCase()}
                          </span>
                          <span className="priority-val-tag">Priority: {priority}</span>
                        </div>
                        <h4 className="exec-rec-item-title">{r.title}</h4>
                        <p className="exec-rec-item-why">
                          <strong>Why:</strong> {plan?.root_cause || r.explanation}
                        </p>
                        {plan?.expected_impact && (
                          <p className="exec-rec-item-impact">
                            <strong>Expected Impact:</strong> {plan.expected_impact}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="exec-rec-card-actions">
                      {onOpenRootCause && r.related_metrics?.[0] && (
                        <button
                          className="btn-sm btn-outline"
                          onClick={() => onOpenRootCause(r.related_metrics[0])}
                        >
                          🔬 View Analysis
                        </button>
                      )}

                      {onStartAction && r.status === "open" && (
                        <button
                          className="btn-sm btn-action start"
                          onClick={() => onStartAction(r.id)}
                        >
                          🚀 Start Action
                        </button>
                      )}

                      <button
                        className="btn-sm btn-ghost replay-btn"
                        onClick={() => setSelectedRecForReplay(r)}
                      >
                        🧠 Why did AI make this decision?
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Decision Replay Modal */}
      {selectedRecForReplay && (
        <AIDecisionReplayModal
          recommendation={selectedRecForReplay}
          onClose={() => setSelectedRecForReplay(null)}
        />
      )}
    </div>
  );
}
