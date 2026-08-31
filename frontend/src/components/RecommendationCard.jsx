import React, { useState, useEffect } from "react";
import { api } from "../api";

function priorityTier(score) {
  if (score >= 60) return { label: "Critical", className: "critical" };
  if (score >= 30) return { label: "Attention", className: "attention" };
  return { label: "Watch", className: "watch" };
}

const AGENT_CLASS = {
  Perceiver: "perceiver",
  AdaptiveWeighter: "adaptive-weighter",
  ContextDetector: "context-detector",
  Evaluator: "evaluator",
  Negotiator: "negotiator",
  Explainer: "explainer",
  ConfidenceEstimator: "confidence-estimator",
  StrategySelector: "strategy-selector",
  GoalOptimizer: "goal-optimizer",
};

export default function RecommendationCard({
  recommendation,
  rank,
  onStatusChange,
  onOpenRootCause,
}) {
  const [open, setOpen] = useState(false);
  const [wasHelpful, setWasHelpful] = useState(null);
  const [comment, setComment] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [outcomeData, setOutcomeData] = useState(null);
  const [outcomeLoading, setOutcomeLoading] = useState(false);

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

  const handleStart = async (e) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await api.startRecommendation(recommendation.id, "Action started by engineer.");
      if (onStatusChange) onStatusChange(recommendation.id, "in_progress");
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolve = async (e) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await api.resolveRecommendation(recommendation.id, "Remediation verified and deployed.");
      if (onStatusChange) onStatusChange(recommendation.id, "actioned");
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleVerify = async (e) => {
    e.stopPropagation();
    setOutcomeLoading(true);
    try {
      const outcome = await api.verifyRecommendation(recommendation.id);
      setOutcomeData(outcome);
    } catch (err) {
      console.error(err);
    } finally {
      setOutcomeLoading(false);
    }
  };

  const handleDismiss = async (e) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await api.updateRecommendationStatus(recommendation.id, "dismissed");
      if (onStatusChange) onStatusChange(recommendation.id, "dismissed");
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(false);
    }
  };

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
        outcome_delta: null,
      });
      setFeedbackSubmitted(true);
      localStorage.setItem(`feedback_${recommendation.id}`, JSON.stringify({ wasHelpful, comment }));
    } catch (err) {
      console.error("Failed to submit feedback", err);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const plan = recommendation.action_plan;
  const confLabel = recommendation.confidence_label || "low";
  const confScore = typeof recommendation.confidence_score === "number" ? recommendation.confidence_score : 0;
  const confEvidenceText = (recommendation.confidence_evidence || []).join("\n");

  const status = recommendation.status || "open";

  return (
    <div className={`rec-card ${tier.className} status-${status}`}>
      <div className="rec-header" onClick={() => setOpen(!open)}>
        <div className="rec-rank">{String(rank).padStart(2, "0")}</div>

        <div className="rec-main">
          <div className="rec-title-row">
            <span className={`tier-badge ${tier.className}`}>{tier.label}</span>
            <span className={`status-pill status-${status}`}>
              {status === "in_progress" ? "⏳ In Progress" : status === "actioned" ? "✓ Resolved" : status === "dismissed" ? "✕ Archived" : "● Open"}
            </span>
            {recommendation.detected_domain && (
              <span className="domain-pill" title={`Detected domain: ${recommendation.detected_domain}`}>
                🏷️ {recommendation.detected_domain}
              </span>
            )}
            <h3 className="rec-title">{recommendation.title}</h3>
          </div>
          <p className="rec-explanation">{recommendation.explanation}</p>
        </div>

        <div className="rec-score-block">
          <div
            className={`confidence-badge confidence-${confLabel}`}
            title={`Confidence: ${confScore.toFixed(2)} (${confLabel.toUpperCase()})\n\n${confEvidenceText}`}
          >
            <span className="conf-dot" />
            {confLabel} {confScore.toFixed(2)}
          </div>

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

      {/* Lifecycle Quick Bar */}
      <div className="rec-lifecycle-bar" onClick={(e) => e.stopPropagation()}>
        <div className="lifecycle-buttons">
          {status === "open" && (
            <button className="btn-action start" onClick={handleStart} disabled={actionLoading}>
              🚀 Start Action
            </button>
          )}
          {status === "in_progress" && (
            <button className="btn-action resolve" onClick={handleResolve} disabled={actionLoading}>
              ✓ Mark Resolved
            </button>
          )}
          {status === "actioned" && (
            <button className="btn-action verify" onClick={handleVerify} disabled={outcomeLoading}>
              {outcomeLoading ? "Analyzing Telemetry…" : "📊 Verify Result"}
            </button>
          )}
          {status !== "dismissed" && (
            <button className="btn-action dismiss" onClick={handleDismiss} disabled={actionLoading}>
              Dismiss
            </button>
          )}
        </div>

        {onOpenRootCause && recommendation.related_metrics?.[0] && (
          <button
            className="btn-link-sm"
            onClick={() => onOpenRootCause(recommendation.related_metrics[0])}
          >
            🔬 Root Cause Trace
          </button>
        )}
      </div>

      {/* Outcome verification banner */}
      {outcomeData && (
        <div className="outcome-verification-banner">
          <div className="outcome-header">
            <span className="outcome-icon">{outcomeData.goal_achieved ? "🎉" : "⚠️"}</span>
            <div>
              <div className="outcome-title">
                {outcomeData.goal_achieved ? "Goal Achieved — Metric Verified" : "Metric Verification Pending Target"}
              </div>
              <div className="outcome-details">
                Before: <strong>{outcomeData.before_value}</strong> → After: <strong>{outcomeData.after_value}</strong> ({outcomeData.improvement_pct > 0 ? "+" : ""}{outcomeData.improvement_pct}% turnaround)
              </div>
            </div>
          </div>
        </div>
      )}

      {open && (
        <div className="reasoning-trail">
          {/* AI Action Plan Grid */}
          {plan && (
            <div className="action-plan-container">
              <div className="action-plan-header">
                <span className="plan-icon">📋</span>
                <span className="plan-title">AI Action Plan & Remediation Guide</span>
              </div>

              <div className="action-plan-grid">
                <div className="plan-item full">
                  <span className="plan-label">Why It Matters</span>
                  <p className="plan-val">{plan.why_it_matters}</p>
                </div>

                <div className="plan-item">
                  <span className="plan-label">Root Cause Analysis</span>
                  <p className="plan-val highlight-amber">{plan.root_cause}</p>
                </div>

                <div className="plan-item">
                  <span className="plan-label">Recommended Action</span>
                  <p className="plan-val highlight-teal">{plan.recommended_action}</p>
                </div>

                <div className="plan-item">
                  <span className="plan-label">Expected Impact</span>
                  <p className="plan-val highlight-teal">{plan.expected_impact}</p>
                </div>

                <div className="plan-item">
                  <span className="plan-label">Estimated Effort</span>
                  <p className="plan-val">{plan.estimated_effort}</p>
                </div>

                <div className="plan-item full">
                  <span className="plan-label">Success Criteria Milestone</span>
                  <p className="plan-val success-box">🎯 {plan.success_criteria}</p>
                </div>
              </div>
            </div>
          )}

          {/* Reasoning Trail */}
          <div className="reasoning-trail-label">Multi-Agent Reasoning Trail</div>
          <ol className="trail-list">
            {recommendation.reasoning_trail.map((step, i) => (
              <li key={i} className="trail-step">
                <span className="trail-node" />
                <span className="trail-text">{step}</span>
              </li>
            ))}
          </ol>

          {/* Feedback Form */}
          <div className="feedback-section" onClick={(e) => e.stopPropagation()}>
            {feedbackSubmitted ? (
              <div className="feedback-success">
                <span>✓</span> Feedback recorded in Bayesian memory. Thank you!
              </div>
            ) : (
              <form onSubmit={handleSubmitFeedback}>
                <div className="feedback-prompt">
                  <span>Was this prioritization helpful?</span>
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
                      placeholder={wasHelpful ? "What made this helpful? (Optional)" : "Please explain what was unhelpful..."}
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
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
