export default function Sidebar({ projects, activeProjectId, onSelectProject, aiEnabled }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-mark">AM</div>
        <div>
          <div className="sidebar-title">Agentic Metrics</div>
          <div className="sidebar-subtitle">Prioritization Agent</div>
        </div>
      </div>

      <div className="sidebar-section-label">Projects</div>
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
            {p.name}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className={`agent-status ${aiEnabled ? "on" : "off"}`}>
          <span className="pulse" />
          {aiEnabled ? "LLM narration active" : "Rule-based reasoning"}
        </div>
      </div>
    </aside>
  );
}
