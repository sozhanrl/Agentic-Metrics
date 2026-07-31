import { useState, useEffect } from "react";
import { api } from "../api";

function priorityTier(score) {
  if (score >= 60) return { label: "Critical", className: "critical" };
  if (score >= 30) return { label: "Attention", className: "attention" };
  return { label: "Watch", className: "watch" };
}

/* Map each agent name to a CSS class for its colored chip */
const AGENT_CLASS = {
  Perceiver:        "perceiver",
  AdaptiveWeighter: "adaptive-weighter",
  Evaluator:        "evaluator",
  Negotiator:       "negotiator",
  Explainer:        "explainer",
};

/* Human-readable action labels */
function actionLabel(action) {
  const map = {
    "static-evaluation":         "Static eval",
    "trend-amplification":       "Trend ↑ amplified",
    "trend-ok":                  "Trend OK",
    "trend-skipped":             "No trend data",
    "skipped":                   "Skipped",
    "no-profile":                "No risk profile",
    "tech-debt-adjustment":      "Tech-debt adj.",
    "risk-tolerance-adjustment": "Risk-tolerance adj.",
    "small-team-adjustment":     "Small-team adj.",
    "team-size-ok":              "Team size OK",
    "scoring":                   "Scored",
    "below-threshold":           "Below threshold",
    "dependency-note":           "Dependency",
    "conflict-penalty":          "Conflict penalty",
    "conflict-noted":            "Conflict noted",
    "explanation":               "Explained",
  };
  return map[action] || action;
}

/* Trend arrow based on slope + direction */
function TrendIndicator({ slope, recommendation }) {
  const hasConflict = !!recommendation.conflict_note;
  const hasSlope    = typeof slope === "number" && slope !== 0;

  if (!hasSlope && !hasConflict) return null;

  let arrow = "→", arrowClass = "trend-flat";
  if (hasSlope) {
    arrow      = slope > 0 ? "↑" : "↓";
    arrowClass = slope > 0 ? "trend-up" : "trend-down";
  }

  return (
    <div className="trend-row">
      {hasSlope && (
        <span className={`trend-indicator ${arrowClass}`}>
          {arrow} slope {slope > 0 ? "+" : ""}{slope.toFixed(3)}/period
        </span>
      )}
      {hasConflict && (
        <span className="conflict-badge" title={recommendation.conflict_note}>
          ⚡ Negotiated — priority reduced
        </span>
      )}
    </div>
  );
}

/* Adaptive Weights pill row */
function WeightsPills({ weights }) {
  if (!weights || Object.keys(weights).length === 0) return null;

  const labels = {
    code_quality: "Code Quality",
    process:      "Process",
    devops:       "DevOps",
  };

  return (
    <div className="weights-section">
      <div className="agent-trace-label">Adaptive weights this run</div>
      <div className="weights-row">
        {Object.entries(weights).map(([cat, val]) => (
          <span key={cat} className={`weight-pill weight-${cat.replace("_", "-")}`}>
            {labels[cat] || cat} ×{Number(val).toFixed(2)}
          </span>
        ))}
      </div>
    </div>
  );
}

/* Agent Trail timeline */
function AgentTrail({ steps }) {
  const [collapsed, setCollapsed] = useState(true);

  if (!steps || steps.length === 0) return null;

  const visibleSteps = collapsed ? steps.slice(0, 4) : steps;

  return (
    <div className="agent-trace-section">
      <div
        className="agent-trace-label clickable"
        onClick={() => setCollapsed((c) => !c)}
        role="button"
        aria-expanded={!collapsed}
      >
        Agent pipeline trace
        <span className="trace-toggle">{collapsed ? `+${steps.length - Math.min(4, steps.length)} more` : "collapse"}</span>
      </div>

      <div className="agent-step-list">
        {visibleSteps.map((step, i) => {
          const agentClass = AGENT_CLASS[step.agent] || "unknown";
          return (
            <div key={i} className="agent-step-row">
              <div className="step-left">
                <span className={`agent-chip agent-chip--${agentClass}`}>{step.agent}</span>
                <span className="action-badge">{actionLabel(step.action)}</span>
              </div>
              <div className="step-detail">{step.detail}</div>
            </div>
          );
        })}
      </div>

      {collapsed && steps.length > 4 && (
        <button
          className="trace-expand-btn"
          onClick={() => setCollapsed(false)}
        >
          Show all {steps.length} pipeline steps
        </button>
      )}
    </div>
  );
}

export default function RecommendationCard({ recommendation, rank, onStatusChange }) {
  const [open, setOpen] = useState(false);
  const [wasHelpful, setWasHelpful] = useState(null);
  const [comment, setComment] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem(`feedback_${recommendation.id}`);
    if (saved) {
      setFeedbackSubmitted(true);
      const parsed = JSON.parse(saved);
      setWasHelpful(parsed.wasHelpful);
      setComment(parsed.comment);
    }
  }, [recommendation.id]);

  const tier = priorityTier(recommendation.priority_score);

  const handleSubmitFeedback = async (e) => {
    e.preventDefault();
    if (wasHelpful === null) return;
    setSubmittingFeedback(true);
    try {
      await api.submitFeedback({
        recommendation_id: parseInt(recommendation.id),
        was_helpful: wasHelpful,
        user_comment: comment || null,
        outcome_metric_id: recommendation.related_metrics?.[0] || null,
        outcome_delta: null
      });
      setFeedbackSubmitted(true);
      localStorage.setItem(`feedback_${recommendation.id}`, JSON.stringify({ wasHelpful, comment }));
    } catch (err) {
      console.error("Failed to submit feedback", err);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const hasAgentTrail = recommendation.agent_trail?.length > 0;
  const hasWeights    = recommendation.adaptive_weights &&
                        Object.keys(recommendation.adaptive_weights).length > 0;

  return (
    <div className={`rec-card ${tier.className}`}>
      <div className="rec-header" onClick={() => setOpen(!open)}>
        <div className="rec-rank">{String(rank).padStart(2, "0")}</div>

        <div className="rec-main">
          <div className="rec-title-row">
            <span className={`tier-badge ${tier.className}`}>{tier.label}</span>
            <h3 className="rec-title">{recommendation.title}</h3>
            {hasAgentTrail && (
              <span className="multi-agent-badge" title="Generated by multi-agent pipeline">
                🤖 Multi-Agent
              </span>
            )}
          </div>
          <p className="rec-explanation">{recommendation.explanation}</p>
        </div>

        <div className="rec-score-block">
          <div className="rec-score">{recommendation.priority_score.toFixed(0)}</div>
          <div className="score-bar-track">
            <div
              className="score-bar-fill"
              style={{ width: `${Math.min(recommendation.priority_score, 100)}%` }}
            />
          </div>
        </div>

        <button className="rec-expand-toggle" aria-label="Toggle reasoning trail">
          {open ? "−" : "+"}
        </button>
      </div>

      {open && (
        <div className="reasoning-trail">

          {/* ── Reasoning Trail ── */}
          <div className="reasoning-trail-label">Agent reasoning trail</div>
          <ol className="trail-list">
            {recommendation.reasoning_trail.map((step, i) => (
              <li key={i} className="trail-step">
                <span className="trail-node" />
                <span className="trail-text">{step}</span>
              </li>
            ))}
          </ol>

          {/* ── Trend + Conflict Note ── */}
          <TrendIndicator
            slope={recommendation.trend_slope}
            recommendation={recommendation}
          />

          {/* ── Adaptive Weights ── */}
          {hasWeights && (
            <WeightsPills weights={recommendation.adaptive_weights} />
          )}

          {/* ── Agent Pipeline Trace ── */}
          {hasAgentTrail && (
            <AgentTrail steps={recommendation.agent_trail} />
          )}

          {/* ── Status + Feedback ── */}
          <div className="rec-actions" onClick={(e) => e.stopPropagation()}>
            <div className="rec-actions-left">
              <label htmlFor={`status-${recommendation.id}`}>Status:</label>
              <select
                id={`status-${recommendation.id}`}
                className="status-select"
                value={recommendation.status}
                onChange={(e) => onStatusChange(recommendation.id, e.target.value)}
              >
                <option value="open">Open</option>
                <option value="acknowledged">Acknowledged</option>
                <option value="actioned">Resolved</option>
                <option value="dismissed">Archived</option>
              </select>
            </div>
          </div>

          <div className="feedback-section" onClick={(e) => e.stopPropagation()}>
            {feedbackSubmitted ? (
              <div className="feedback-success">
                <span>✓</span> Feedback submitted. Thank you for training the agent!
              </div>
            ) : (
              <form onSubmit={handleSubmitFeedback}>
                <div className="feedback-prompt">
                  <span>Was this recommendation helpful?</span>
                  <div className="feedback-buttons">
                    <button
                      type="button"
                      className={`feedback-btn yes ${wasHelpful === true ? "active" : ""}`}
                      onClick={() => setWasHelpful(true)}
                    >
                      👍 Yes
                    </button>
                    <button
                      type="button"
                      className={`feedback-btn no ${wasHelpful === false ? "active" : ""}`}
                      onClick={() => setWasHelpful(false)}
                    >
                      👎 No
                    </button>
                  </div>
                </div>

                {wasHelpful !== null && (
                  <div className="feedback-form-expanded">
                    <textarea
                      className="feedback-comment-input"
                      placeholder={wasHelpful ? "What made this recommendation helpful? (Optional)" : "Please explain what was unhelpful so we can improve..."}
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      required={wasHelpful === false}
                    />
                    <button
                      type="submit"
                      className="feedback-submit-btn"
                      disabled={submittingFeedback}
                    >
                      {submittingFeedback ? "Submitting..." : "Submit Feedback"}
                    </button>
                  </div>
                )}
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
