import React, { useState, useEffect } from "react";
import { api } from "../api";

export default function TimelineView({ projectId }) {
  const [events, setEvents] = useState([]);
  const [filterType, setFilterType] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    const evType = filterType === "all" ? null : filterType;
    api.getTimeline(projectId, evType)
      .then((res) => setEvents(res))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId, filterType]);

  const EVENT_ICONS = {
    rec_generated: "⚡",
    rec_resolved: "✓",
    ai_intervention: "🤖",
    metric_degraded: "📉",
    metric_improved: "📈",
    anomaly: "⚠️",
    deployment: "🚀",
    commit: "💻",
  };

  return (
    <div className="timeline-container">
      <div className="timeline-header">
        <div>
          <h2>Project Activity & Event Timeline</h2>
          <span className="section-caption">Historical chronology of metric fluctuations, recommendations, and AI interventions</span>
        </div>

        <div className="timeline-filters">
          <select
            className="filter-select"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="all">All Event Types</option>
            <option value="rec_generated">Recommendations Generated</option>
            <option value="rec_resolved">Recommendations Resolved</option>
            <option value="ai_intervention">AI Interventions</option>
            <option value="anomaly">Anomalies</option>
          </select>
        </div>
      </div>

      {loading && (
        <div className="section-loading">
          <div className="spinner" />
          <p>Loading project timeline stream…</p>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      {!loading && events.length === 0 && (
        <div className="empty-state">
          <p>No timeline events recorded yet for this filter.</p>
        </div>
      )}

      <div className="timeline-stream">
        {events.map((ev) => (
          <div key={ev.id} className={`timeline-card type-${ev.event_type}`}>
            <div className="timeline-icon-box">
              <span className="timeline-icon">{EVENT_ICONS[ev.event_type] || "📌"}</span>
            </div>

            <div className="timeline-card-content">
              <div className="timeline-card-top">
                <h4 className="timeline-title">{ev.title}</h4>
                <span className="timeline-date">
                  {new Date(ev.created_at).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              {ev.description && <p className="timeline-desc">{ev.description}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
