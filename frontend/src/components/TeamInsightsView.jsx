import React, { useState, useEffect } from "react";
import { api } from "../api";

export default function TeamInsightsView({ projectId }) {
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    api.getTeamInsights(projectId)
      .then((res) => setInsights(res))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="section-loading">
        <div className="spinner" />
        <p>Analyzing engineering throughput & workflow telemetry…</p>
      </div>
    );
  }

  if (error) return <div className="error-banner">{error}</div>;
  if (!insights) return null;

  return (
    <div className="team-insights-container">
      <div className="team-header">
        <div>
          <h2>Engineering Team & System Insights</h2>
          <p className="team-subtitle">
            System-level workflow indicators and delivery bottleneck discovery. (Focuses on engineering-system health, never individual worker metrics)
          </p>
        </div>
      </div>

      {/* KPI Cards Strip */}
      <div className="team-kpis-grid">
        <div className="team-kpi-card">
          <div className="team-kpi-val">{insights.pr_throughput}</div>
          <div className="team-kpi-label">PR Throughput / Wk</div>
        </div>

        <div className="team-kpi-card">
          <div className="team-kpi-val">{insights.avg_pr_review_hours}h</div>
          <div className="team-kpi-label">Avg PR Review Latency</div>
        </div>

        <div className="team-kpi-card">
          <div className="team-kpi-val">{insights.commit_activity_weekly}</div>
          <div className="team-kpi-label">Weekly Commits</div>
        </div>

        <div className="team-kpi-card">
          <div className="team-kpi-val">{insights.avg_issue_resolution_days}d</div>
          <div className="team-kpi-label">Avg Issue Lead Time</div>
        </div>
      </div>

      {/* System Bottlenecks Box */}
      <div className="bottlenecks-card">
        <div className="bottlenecks-header">
          <span className="bottleneck-icon">⚠️</span>
          <h4>System Bottleneck Indicators</h4>
        </div>
        <ul className="bottleneck-list">
          {insights.bottleneck_indicators?.map((b, i) => (
            <li key={i} className="bottleneck-item">
              {b}
            </li>
          ))}
        </ul>
      </div>

      {/* Workload distribution cohorts */}
      <div className="workload-section">
        <h3>Engineering Workload Distribution</h3>
        <table className="workload-table">
          <thead>
            <tr>
              <th>Contributor Cohort</th>
              <th>Pull Requests</th>
              <th>Commits</th>
              <th>Code Volume</th>
            </tr>
          </thead>
          <tbody>
            {insights.workload_distribution?.map((c, i) => (
              <tr key={i}>
                <td><strong>{c.login}</strong></td>
                <td>{c.pull_requests} PRs</td>
                <td>{c.commits} commits</td>
                <td>{c.lines_changed.toLocaleString()} lines</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
