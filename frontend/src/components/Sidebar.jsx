import React from "react";

export default function Sidebar({
  projects,
  activeProjectId,
  onSelectProject,
  aiEnabled,
  appView,
  onSelectView,
  unreadAlertsCount = 0,
  onOpenAlerts,
  onOpenAssistant,
}) {
  const navItems = [
    { key: "project", label: "🏗️ Dashboard" },
    { key: "executive", label: "👔 Executive View" },
    { key: "analytics", label: "📊 Feedback Analytics" },
    { key: "risks", label: "🛡️ Predictive Risks" },
    { key: "timeline", label: "⏱️ Event Timeline" },
    { key: "team", label: "👥 Team Insights" },
    { key: "graph", label: "🧬 Causal Graph" },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-mark">AI</div>
        <div>
          <div className="sidebar-title">Engineering Intelligence</div>
          <div className="sidebar-subtitle">Multi-Agent Quality Platform</div>
        </div>
      </div>

      <div className="sidebar-quick-tools">
        <button className="sidebar-quick-btn ai-btn" onClick={onOpenAssistant}>
          <span>🤖</span> AI Assistant
        </button>
        <button className="sidebar-quick-btn alerts-btn" onClick={onOpenAlerts}>
          <span>🔔</span> Alerts
          {unreadAlertsCount > 0 && <span className="alert-count-pill">{unreadAlertsCount}</span>}
        </button>
      </div>

      <div className="sidebar-section-label">Navigation Views</div>
      <nav className="sidebar-nav">
        {navItems.map(({ key, label }) => (
          <button
            key={key}
            className={`sidebar-nav-item ${appView === key ? "active" : ""}`}
            onClick={() => onSelectView(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="sidebar-section-label">Projects ({projects.length})</div>
      <nav className="sidebar-projects">
        {projects.length === 0 && (
          <div className="sidebar-empty">No projects yet</div>
        )}
        {projects.map((p) => (
          <button
            key={p.id}
            className={`sidebar-project ${p.id === activeProjectId ? "active" : ""}`}
            onClick={() => onSelectProject(p.id)}
          >
            <span className="dot" data-source={p.source} />
            <span className="project-name-text">{p.name}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className={`agent-status ${aiEnabled ? "on" : "off"}`}>
          <span className="pulse" />
          {aiEnabled ? "Claude Narrative Active" : "Multi-Agent Bayesian Pipeline"}
        </div>
      </div>
    </aside>
  );
}
