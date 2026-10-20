import React from "react";

export function ProcessDataNotice({ status, onSeedDemo }) {
  if (status?.sufficient_for_training) {
    return (
      <div className="process-devops-ready-banner">
        <span className="banner-icon">✓</span>
        <div>
          <strong>Historical Process Records Active:</strong> Found {status.historical_records} sprint observations.
          Sprint Velocity Forecast, Cycle Time Forecast, and Sprint Delay Risk are actively projected.
        </div>
      </div>
    );
  }

  return (
    <div className="process-devops-empty-card">
      <div className="empty-card-header">
        <span className="empty-card-icon">📋</span>
        <div>
          <h4 className="empty-card-title">Missing Historical Process Data</h4>
          <span className="empty-card-subtitle">
            Sprint Velocity Forecast &bull; Cycle Time Forecast &bull; Delay Risk &bull; Spillover Rate
          </span>
        </div>
      </div>
      <p className="empty-card-message">
        The three supplied CSV datasets (<code>SoftwareDefectDataset.csv</code>, <code>OnlyTrivial_dt.csv</code>, <code>OnlyNonTrivial_dt.csv</code>)
        are code quality and refactoring datasets, not sprint or issue tracking history.
        Process forecasting requires genuine sprint velocity and story cycle-time logs from an issue tracker (Jira, Azure DevOps).
        <strong> No fake model is trained on unrelated code metrics.</strong>
      </p>
      <div className="empty-card-actions">
        <span className="empty-card-tag">Required: 30+ Sprint Records</span>
        <span className="empty-card-tag">Current: {status?.historical_records || 0} Records</span>
        {onSeedDemo && (
          <button className="btn-seed-banner" onClick={onSeedDemo}>
            Seed Demo Sprint History
          </button>
        )}
      </div>
    </div>
  );
}

export function DevopsDataNotice({ status, onSeedDemo }) {
  if (status?.sufficient_for_training) {
    return (
      <div className="process-devops-ready-banner">
        <span className="banner-icon">✓</span>
        <div>
          <strong>Historical CI/CD Telemetry Active:</strong> Found {status.historical_records} deployment observations.
          Deployment Failure Probability, MTTR, and Rollback Rate predictions are actively evaluated.
        </div>
      </div>
    );
  }

  return (
    <div className="process-devops-empty-card">
      <div className="empty-card-header">
        <span className="empty-card-icon">🚀</span>
        <div>
          <h4 className="empty-card-title">Missing CI/CD & Deployment Records</h4>
          <span className="empty-card-subtitle">
            Deployment Failure Probability &bull; Success Rate &bull; MTTR &bull; Rollback Rate
          </span>
        </div>
      </div>
      <p className="empty-card-message">
        The supplied CSV datasets contain static code metrics and refactoring operations, not deployment history.
        DevOps reliability and deployment failure predictions require historical deployment logs, build results,
        rollbacks, and incident records from CI/CD pipelines (GitHub Actions, Jenkins, ArgoCD).
        <strong> Predictions will activate once deployment logs are connected.</strong>
      </p>
      <div className="empty-card-actions">
        <span className="empty-card-tag">Required: CI/CD Deployment Logs</span>
        <span className="empty-card-tag">Current: {status?.historical_records || 0} Records</span>
        {onSeedDemo && (
          <button className="btn-seed-banner" onClick={onSeedDemo}>
            Seed Demo Deployment History
          </button>
        )}
      </div>
    </div>
  );
}
