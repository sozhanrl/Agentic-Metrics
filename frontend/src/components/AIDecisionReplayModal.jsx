import React from "react";

export default function AIDecisionReplayModal({ recommendation, onClose }) {
  if (!recommendation) return null;

  const plan = recommendation.action_plan;
  const confLabel = recommendation.confidence_label || "high";

  const pipelineSteps = [
    {
      stage: "Metric Signal",
      icon: "📡",
      label: "Telemetry Observation",
      detail: recommendation.explanation,
    },
    {
      stage: "Perceiver",
      icon: "🔍",
      label: "Statistical Boundary Analysis",
      detail: `Metric trend and deviation evaluated against nominal threshold bands.`,
    },
    {
      stage: "Adaptive Weighting",
      icon: "⚖️",
      label: "Category Weighting Adjustment",
      detail: "Category priorities dynamically weighted based on risk profile and historical momentum.",
    },
    {
      stage: "Context Detection",
      icon: "🏷️",
      label: "Domain Context Recognition",
      detail: `Domain context: ${recommendation.detected_domain || "Software Engineering Systems"}.`,
    },
    {
      stage: "Evaluator",
      icon: "🧮",
      label: "Impact & Cost Estimation",
      detail: plan ? `Estimated effort: ${plan.estimated_effort}. Expected impact: ${plan.expected_impact}.` : "Evaluated priority score.",
    },
    {
      stage: "Negotiation",
      icon: "🤝",
      label: "Multi-Goal Tradeoff Balancing",
      detail: recommendation.conflict_note || "Balanced against capacity and risk budget constraints.",
    },
    {
      stage: "Evidence-Adaptive Arbitration",
      icon: "🧬",
      label: "Bayesian / Causal Graph Fusion",
      detail: "Per-metric evidence arbitration combining empirical priors and causal dependency propagation.",
    },
    {
      stage: "Confidence & Final Priority",
      icon: "🎯",
      label: "Scored Recommendation",
      detail: `Priority Score: ${recommendation.priority_score?.toFixed(0)} | Confidence Rating: ${confLabel.toUpperCase()}`,
    },
  ];

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content wide decision-replay-modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div className="modal-title-container">
            <h3 className="modal-title">🧠 Why did AI make this decision?</h3>
            <span className="modal-subtitle">
              Auditable Multi-Agent Decision Lineage for: <strong>"{recommendation.title}"</strong>
            </span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            &times;
          </button>
        </header>

        <div className="decision-replay-body">
          <div className="pipeline-flow-diagram">
            {pipelineSteps.map((step, idx) => (
              <React.Fragment key={idx}>
                <div className="flow-step-card">
                  <div className="flow-step-header">
                    <span className="flow-icon">{step.icon}</span>
                    <span className="flow-stage-name">{step.stage}</span>
                  </div>
                  <h4 className="flow-step-label">{step.label}</h4>
                  <p className="flow-step-detail">{step.detail}</p>
                </div>
                {idx < pipelineSteps.length - 1 && (
                  <div className="flow-connector">
                    <span className="connector-arrow">↓</span>
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>

          <div className="decision-summary-footer">
            <div className="summary-box">
              <span className="summary-box-title">🎯 Final Recommendation Output</span>
              <p>
                Priority Score: <strong>{recommendation.priority_score?.toFixed(0)}</strong> &bull;
                Confidence: <strong>{confLabel.toUpperCase()}</strong> &bull;
                Status: <strong>{recommendation.status}</strong>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
