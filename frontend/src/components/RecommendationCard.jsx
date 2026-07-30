import { useState, useEffect } from "react";
import { api } from "../api";

function priorityTier(score) {
  if (score >= 60) return { label: "Critical", className: "critical" };
  if (score >= 30) return { label: "Attention", className: "attention" };
  return { label: "Watch", className: "watch" };
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

  return (
    <div className={`rec-card ${tier.className}`}>
      <div className="rec-header" onClick={() => setOpen(!open)}>
        <div className="rec-rank">{String(rank).padStart(2, "0")}</div>

        <div className="rec-main">
          <div className="rec-title-row">
            <span className={`tier-badge ${tier.className}`}>{tier.label}</span>
            <h3 className="rec-title">{recommendation.title}</h3>
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
          <div className="reasoning-trail-label">Agent reasoning trail</div>
          <ol className="trail-list">
            {recommendation.reasoning_trail.map((step, i) => (
              <li key={i} className="trail-step">
                <span className="trail-node" />
                <span className="trail-text">{step}</span>
              </li>
            ))}
          </ol>

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
