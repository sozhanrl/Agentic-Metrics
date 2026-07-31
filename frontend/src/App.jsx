import { useEffect, useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import RecommendationCard from "./components/RecommendationCard";
import MetricCard from "./components/MetricCard";
import FeedbackAnalytics from "./components/FeedbackAnalytics";
import { api } from "./api";
import "./App.css";

const CATEGORY_LABELS = {
  code_quality: "Code Quality",
  process: "Process",
  devops: "DevOps",
};

const METRIC_TARGETS = {
  code_churn: { target: 15, unit: "%", higherIsBetter: false },
  cyclomatic_complexity: { target: 10, unit: "count", higherIsBetter: false },
  test_coverage: { target: 80, unit: "%", higherIsBetter: true },
  defect_density: { target: 1.0, unit: "defects/kloc", higherIsBetter: false },
  sprint_velocity: { target: 30, unit: "story points", higherIsBetter: true },
  cycle_time: { target: 3, unit: "days", higherIsBetter: false },
  lead_time: { target: 7, unit: "days", higherIsBetter: false },
  deployment_frequency: { target: 3, unit: "per week", higherIsBetter: true },
  change_failure_rate: { target: 15, unit: "%", higherIsBetter: false },
  mttr: { target: 4, unit: "hours", higherIsBetter: false },
};

export default function App() {
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [metrics, setMetrics] = useState([]);
  const [metricsHistory, setMetricsHistory] = useState({});
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProject, setNewProject] = useState({ name: "", source: "github", external_id: "" });
  const [aiEnabled, setAiEnabled] = useState(false);

  // Top-level view: "project" | "analytics"
  const [appView, setAppView] = useState("project");

  // Filter & Queue tabs states
  const [activeTab, setActiveTab] = useState("open");
  const [searchQuery, setSearchQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("all");

  // Modal state
  const [selectedMetric, setSelectedMetric] = useState(null);
  const [hoveredPoint, setHoveredPoint] = useState(null);

  // Weight Lens panel
  const [weightLensOpen, setWeightLensOpen] = useState(false);
  const [weightLens, setWeightLens] = useState(null);
  const [weightLensLoading, setWeightLensLoading] = useState(false);

  const loadProjectData = useCallback(async (projectId) => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [metricsData, recsData, historyData] = await Promise.all([
        api.getLatestMetrics(projectId),
        api.getRecommendations(projectId),
        api.getAllMetricsHistory(projectId).catch(() => ({})),
      ]);
      setMetrics(metricsData);
      setRecommendations(recsData);
      setMetricsHistory(historyData || {});
      setAiEnabled(recsData.some((r) => r.ai_narrated));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    api.getProjects().then((data) => {
      setProjects(data);
      if (data.length > 0) setActiveProjectId(data[0].id);
    }).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (activeProjectId) {
      loadProjectData(activeProjectId);
      setSelectedMetric(null);
    }
  }, [activeProjectId, loadProjectData]);

  async function handleCreateProject(e) {
    e.preventDefault();
    try {
      const created = await api.createProject(newProject);
      setProjects((prev) => [...prev, created]);
      setActiveProjectId(created.id);
      setShowNewProject(false);
      setNewProject({ name: "", source: "github", external_id: "" });
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleSeed() {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      await api.seedDemoData(activeProjectId);
      await loadProjectData(activeProjectId);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    if (!activeProjectId) return;
    setGenerating(true);
    setError(null);
    try {
      const recs = await api.generateRecommendations(activeProjectId);
      setRecommendations(recs);
      setAiEnabled(recs.some((r) => r.ai_narrated));
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  }

  async function handleStatusChange(recId, status) {
    try {
      const updated = await api.updateRecommendationStatus(recId, status);
      setRecommendations((prev) =>
        prev.map((r) => (r.id === recId ? { ...r, status: updated.status } : r))
      );
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleLoadWeightLens() {
    if (!activeProjectId) return;
    setWeightLensLoading(true);
    try {
      const data = await api.getWeightComparison(activeProjectId);
      setWeightLens(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setWeightLensLoading(false);
    }
  }

  function handleToggleWeightLens() {
    setWeightLensOpen((o) => {
      const next = !o;
      if (next && !weightLens) handleLoadWeightLens();
      return next;
    });
  }

  // Get count of recommendations by status
  const getTabCount = (status) => {
    return recommendations.filter((r) => r.status === status).length;
  };

  const openRecsCount = getTabCount("open");
  const criticalCount = recommendations.filter((r) => r.status === "open" && r.priority_score >= 60).length;

  // Filter recommendations
  const filteredRecs = recommendations.filter((rec) => {
    const matchesStatus = rec.status === activeTab;
    const matchesSearch = searchQuery
      ? rec.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        rec.explanation.toLowerCase().includes(searchQuery.toLowerCase())
      : true;

    let matchesPriority = true;
    if (priorityFilter !== "all") {
      if (priorityFilter === "critical") matchesPriority = rec.priority_score >= 60;
      else if (priorityFilter === "attention") matchesPriority = rec.priority_score >= 30 && rec.priority_score < 60;
      else if (priorityFilter === "watch") matchesPriority = rec.priority_score < 30;
    }

    return matchesStatus && matchesSearch && matchesPriority;
  });

  const metricsByCategory = metrics.reduce((acc, m) => {
    (acc[m.category] ||= []).push(m);
    return acc;
  }, {});

  // Render modal chart SVG
  const renderHistoryChart = (metric) => {
    const points = metricsHistory[metric.metric_id] || [];
    if (points.length === 0) {
      return (
        <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          No historical data points available yet.
        </div>
      );
    }

    const targetDef = METRIC_TARGETS[metric.metric_key];
    const targetVal = targetDef?.target;

    const values = points.map((p) => p.value);
    if (targetVal !== undefined) values.push(targetVal);

    const maxVal = Math.max(...values, 0) * 1.1;
    const minVal = Math.min(...values, 0) * 0.9;
    const valRange = maxVal - minVal || 10;

    const width = 580;
    const height = 200;
    const paddingX = 40;
    const paddingY = 20;

    const getX = (index) => {
      if (points.length <= 1) return width / 2;
      return paddingX + (index * (width - 2 * paddingX)) / (points.length - 1);
    };

    const getY = (val) => {
      return height - paddingY - ((val - minVal) / valRange) * (height - 2 * paddingY);
    };

    // Construct path line
    const pathD = points.reduce((acc, p, i) => {
      const x = getX(i);
      const y = getY(p.value);
      return acc + `${i === 0 ? "M" : "L"} ${x} ${y}`;
    }, "");

    const targetY = targetVal !== undefined ? getY(targetVal) : null;

    // Get color based on category
    const categoryColors = {
      code_quality: "var(--amber)",
      process: "var(--teal)",
      devops: "var(--rose)",
    };
    const chartColor = categoryColors[metric.category] || "var(--violet)";

    return (
      <div className="modal-chart-svg-container">
        <svg className="modal-chart-svg" viewBox={`0 0 ${width} ${height}`}>
          {/* Horizontal Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const val = minVal + ratio * valRange;
            const y = getY(val);
            return (
              <g key={ratio}>
                <line className="chart-grid-line" x1={paddingX} y1={y} x2={width - paddingX} y2={y} />
                <text className="chart-axis-text" x={paddingX - 10} y={y + 4} textAnchor="end">
                  {val.toFixed(1)}
                </text>
              </g>
            );
          })}

          {/* Target Line */}
          {targetY !== null && (
            <g>
              <line
                className="chart-target-line"
                x1={paddingX}
                y1={targetY}
                x2={width - paddingX}
                y2={targetY}
                stroke={chartColor}
                opacity="0.4"
              />
              <text
                x={width - paddingX - 10}
                y={targetY - 6}
                fill={chartColor}
                fontSize="10"
                fontFamily="var(--font-mono)"
                textAnchor="end"
                opacity="0.8"
              >
                Target: {targetVal}
                {metric.unit}
              </text>
            </g>
          )}

          {/* Line Path */}
          <path className="chart-line-glow" d={pathD} stroke={chartColor} />
          <path className="chart-line" d={pathD} stroke={chartColor} />

          {/* Points */}
          {points.map((p, i) => {
            const cx = getX(i);
            const cy = getY(p.value);
            const isHovered = hoveredPoint && hoveredPoint.id === p.id;
            return (
              <circle
                key={p.id}
                cx={cx}
                cy={cy}
                r={isHovered ? 6 : 4}
                className="chart-point"
                fill={chartColor}
                stroke="var(--surface-opaque)"
                onMouseEnter={() => setHoveredPoint({ ...p, cx, cy })}
                onMouseLeave={() => setHoveredPoint(null)}
              />
            );
          })}
        </svg>

        {/* Hover Tooltip */}
        {hoveredPoint && (
          <div
            className="chart-tooltip-box"
            style={{
              position: "absolute",
              left: `${hoveredPoint.cx + 10}px`,
              top: `${hoveredPoint.cy - 50}px`,
              zIndex: 10,
            }}
          >
            <div className="chart-tooltip-val">
              {hoveredPoint.value.toLocaleString()} {metric.unit}
            </div>
            <div className="chart-tooltip-date">
              {new Date(hoveredPoint.recorded_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="app-shell">
      <Sidebar
        projects={projects}
        activeProjectId={activeProjectId}
        onSelectProject={setActiveProjectId}
        aiEnabled={aiEnabled}
      />

      <main className="main-panel">
        <header className="top-bar">
          <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
            <div>
              <h1 className="page-title">
                {appView === "analytics"
                  ? "Feedback Analytics"
                  : projects.find((p) => p.id === activeProjectId)?.name || "No project selected"}
              </h1>
              <p className="page-subtitle">
                {appView === "analytics"
                  ? "AI recommendation helpfulness insights"
                  : "Telemetry-driven prioritization & actions"}
              </p>
            </div>
            {/* View switcher */}
            <div style={{
              display: "flex", gap: 4,
              background: "var(--surface-raised)",
              border: "1px solid var(--border)",
              borderRadius: 10, padding: 3,
              marginLeft: 8,
            }}>
              {[
                { key: "project",   label: "🏗️ Dashboard" },
                { key: "analytics", label: "📊 Analytics" },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setAppView(key)}
                  style={{
                    border: "none", cursor: "pointer",
                    padding: "5px 14px", borderRadius: 7, fontSize: 12, fontWeight: 600,
                    background: appView === key ? "var(--accent-primary)" : "transparent",
                    color: appView === key ? "#fff" : "var(--text-muted)",
                    transition: "all 0.2s",
                  }}
                >{label}</button>
              ))}
            </div>
          </div>

          <div className="top-actions">
            <button className="btn ghost" onClick={() => setShowNewProject((s) => !s)}>
              + New project
            </button>
            <button className="btn secondary" onClick={handleSeed} disabled={!activeProjectId || loading}>
              Seed demo data
            </button>
            <button className="btn primary" onClick={handleGenerate} disabled={!activeProjectId || generating}>
              {generating ? "Reasoning…" : "Run agent"}
            </button>
          </div>
        </header>

        {showNewProject && (
          <form className="new-project-form" onSubmit={handleCreateProject}>
            <input
              placeholder="Project name"
              value={newProject.name}
              onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
              required
            />
            <select
              value={newProject.source}
              onChange={(e) => setNewProject({ ...newProject, source: e.target.value })}
            >
              <option value="github">GitHub</option>
              <option value="azure_devops">Azure DevOps</option>
              <option value="sonarqube">SonarQube</option>
            </select>
            <input
              placeholder="External ID / repo slug"
              value={newProject.external_id}
              onChange={(e) => setNewProject({ ...newProject, external_id: e.target.value })}
              required
            />
            <button type="submit" className="btn primary">Create</button>
          </form>
        )}

        {error && <div className="error-banner">{error}</div>}

        {/* Analytics view — always renderable, no project required */}
        {appView === "analytics" && (
          <div style={{ padding: "24px 0" }}>
            <FeedbackAnalytics />
          </div>
        )}

        {appView === "project" && !activeProjectId && !error && (
          <div className="empty-state">
            <p>No project selected yet. Create one to get started.</p>
          </div>
        )}

        {appView === "project" && activeProjectId && (
          <>
            <section className="kpi-strip">
              <div className="kpi-card">
                <div className="kpi-value">{openRecsCount}</div>
                <div className="kpi-label">Open recommendations</div>
              </div>
              <div className="kpi-card critical">
                <div className="kpi-value">{criticalCount}</div>
                <div className="kpi-label">Critical priority (Active)</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-value">{metrics.length}</div>
                <div className="kpi-label">Metrics tracked</div>
              </div>
            </section>

            {/* ── Weight Lens Panel ── */}
            <div className="weight-lens">
              <div
                className={`weight-lens-header ${weightLensOpen ? "open" : ""}`}
                onClick={handleToggleWeightLens}
              >
                <div className="weight-lens-title">
                  <span className="weight-lens-icon">⚖️</span>
                  Weight Lens
                  <span className="weight-lens-subtitle">Base prior → Self-learned → Adaptive context</span>
                </div>
                <div className="weight-lens-actions" onClick={(e) => e.stopPropagation()}>
                  {weightLensOpen && (
                    <button
                      className="weight-lens-refresh"
                      onClick={handleLoadWeightLens}
                      disabled={weightLensLoading}
                    >
                      {weightLensLoading ? "Loading…" : "↺ Refresh"}
                    </button>
                  )}
                  <span className={`weight-lens-chevron ${weightLensOpen ? "open" : ""}`}>▼</span>
                </div>
              </div>

              {weightLensOpen && (
                <div className="weight-lens-body">
                  {weightLensLoading && !weightLens && (
                    <div style={{ color: "var(--text-muted)", fontSize: "13px" }}>Loading weight data…</div>
                  )}

                  {weightLens && (
                    <>
                      {!weightLens.has_risk_profile && (
                        <div className="weight-lens-no-profile">
                          ⚠️ No risk profile set for this project — adaptive context equals self-learned weights.
                          Set a risk profile via the API to enable context-aware adjustments.
                        </div>
                      )}

                      <table className="weight-table">
                        <thead>
                          <tr>
                            <th>Category</th>
                            <th>Base Prior</th>
                            <th>Self-Learned</th>
                            <th>Adaptive Context</th>
                            <th>Effective</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.keys(weightLens.base_prior).map((cat) => {
                            const base  = weightLens.base_prior[cat];
                            const sl    = weightLens.self_learned[cat];
                            const adapt = weightLens.adaptive_context[cat];
                            const eff   = weightLens.effective[cat];
                            const slChanged    = Math.abs(sl - base) > 0.005;
                            const adaptChanged = Math.abs(adapt - sl) > 0.005;
                            const effDelta = eff - base;
                            const labels = { code_quality: "Code Quality", process: "Process", devops: "DevOps" };
                            return (
                              <tr key={cat}>
                                <td className={`wt-category ${cat}`}>{labels[cat] || cat}</td>
                                <td className="wt-value">{base.toFixed(3)}</td>
                                <td className={`wt-value ${slChanged ? "changed" : ""}`}>
                                  {sl.toFixed(3)}
                                  {slChanged && (
                                    <span className={`weight-delta ${sl > base ? "up" : "down"}`}>
                                      {sl > base ? "+" : ""}{(sl - base).toFixed(3)}
                                    </span>
                                  )}
                                </td>
                                <td className={`wt-value ${adaptChanged ? "changed" : ""}`}>
                                  {adapt.toFixed(3)}
                                  {adaptChanged && (
                                    <span className={`weight-delta ${adapt > sl ? "up" : "down"}`}>
                                      {adapt > sl ? "+" : ""}{(adapt - sl).toFixed(3)}
                                    </span>
                                  )}
                                </td>
                                <td className="wt-effective">
                                  {eff.toFixed(3)}
                                  {Math.abs(effDelta) > 0.005 && (
                                    <span className={`weight-delta ${effDelta > 0 ? "up" : "down"}`}>
                                      {effDelta > 0 ? "+" : ""}{effDelta.toFixed(3)} vs base
                                    </span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>

                      {weightLens.adaptive_steps?.length > 0 && (
                        <div className="weight-lens-steps">
                          <div className="weight-lens-steps-label">Adaptive context reasoning</div>
                          {weightLens.adaptive_steps.map((step, i) => (
                            <div key={i} className="weight-lens-step">
                              <span className="wl-step-agent">{step.agent}</span>
                              {step.detail}
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>

            <div className="content-grid">
              <section className="priority-queue">
                <div className="section-heading">
                  <h2>Priority queue</h2>
                  <span className="section-caption">Telemetry-driven, weighted suggestions</span>
                </div>

                {/* Filters and search */}
                <div className="queue-controls">
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Search recommendations..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <select
                    className="filter-select"
                    value={priorityFilter}
                    onChange={(e) => setPriorityFilter(e.target.value)}
                  >
                    <option value="all">All Priorities</option>
                    <option value="critical">Critical (&gt;= 60)</option>
                    <option value="attention">Attention (30 - 59)</option>
                    <option value="watch">Watch (&lt; 30)</option>
                  </select>
                </div>

                {/* Queue status tabs */}
                <div className="tab-strip">
                  <button
                    className={`tab-btn ${activeTab === "open" ? "active" : ""}`}
                    onClick={() => setActiveTab("open")}
                  >
                    Active <span className="tab-badge">{getTabCount("open")}</span>
                  </button>
                  <button
                    className={`tab-btn ${activeTab === "acknowledged" ? "active" : ""}`}
                    onClick={() => setActiveTab("acknowledged")}
                  >
                    Acknowledged <span className="tab-badge">{getTabCount("acknowledged")}</span>
                  </button>
                  <button
                    className={`tab-btn ${activeTab === "actioned" ? "active" : ""}`}
                    onClick={() => setActiveTab("actioned")}
                  >
                    Resolved <span className="tab-badge">{getTabCount("actioned")}</span>
                  </button>
                  <button
                    className={`tab-btn ${activeTab === "dismissed" ? "active" : ""}`}
                    onClick={() => setActiveTab("dismissed")}
                  >
                    Archived <span className="tab-badge">{getTabCount("dismissed")}</span>
                  </button>
                </div>

                {filteredRecs.length === 0 && (
                  <div className="empty-state">
                    <p>No recommendations found for this category or filter.</p>
                  </div>
                )}

                <div className="rec-list">
                  {filteredRecs.map((rec, i) => (
                    <RecommendationCard
                      key={rec.id}
                      recommendation={rec}
                      rank={i + 1}
                      onStatusChange={handleStatusChange}
                    />
                  ))}
                </div>
              </section>

              <section className="metrics-panel">
                <div className="section-heading">
                  <h2>Metrics Panel</h2>
                  <span className="section-caption">Click a card to view detailed history</span>
                </div>

                {Object.entries(metricsByCategory).map(([category, list]) => (
                  <div key={category} className="metric-category" data-category={category}>
                    <div className="metric-category-label">
                      {CATEGORY_LABELS[category] || category}
                    </div>
                    <div className="metric-grid">
                      {list.map((m) => (
                        <MetricCard
                          key={m.id}
                          metric={m}
                          history={metricsHistory[m.metric_id] || []}
                          onClick={() => setSelectedMetric(m)}
                        />
                      ))}
                    </div>
                  </div>
                ))}

                {metrics.length === 0 && (
                  <div className="empty-state">
                    <p>No metrics recorded yet.</p>
                  </div>
                )}
              </section>
            </div>
          </>
        )}
      </main>

      {/* Metric Detail Modal */}
      {selectedMetric && (
        <div className="modal-backdrop" onClick={() => setSelectedMetric(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <header className="modal-header">
              <div className="modal-title-container">
                <h3 className="modal-title">{selectedMetric.display_name}</h3>
                <span className="modal-subtitle">
                  Historical telemetry &bull; {CATEGORY_LABELS[selectedMetric.category] || selectedMetric.category}
                </span>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedMetric(null)}>
                &times;
              </button>
            </header>
            <div className="modal-body">
              <div className="modal-chart-container">
                {renderHistoryChart(selectedMetric)}
              </div>
              <div className="modal-meta-grid">
                <div className="modal-meta-item">
                  <div className="modal-meta-label">Current Value</div>
                  <div className="modal-meta-value">
                    {selectedMetric.value.toLocaleString()} {selectedMetric.unit}
                  </div>
                </div>
                <div className="modal-meta-item">
                  <div className="modal-meta-label">Target Threshold</div>
                  <div className="modal-meta-value highlight-amber">
                    {METRIC_TARGETS[selectedMetric.metric_key]?.target || "N/A"}{" "}
                    {selectedMetric.unit}
                  </div>
                </div>
                <div className="modal-meta-item">
                  <div className="modal-meta-label">Total Logs</div>
                  <div className="modal-meta-value highlight-teal">
                    {(metricsHistory[selectedMetric.metric_id] || []).length} recorded
                  </div>
                </div>
                <div className="modal-meta-item">
                  <div className="modal-meta-label">Direction</div>
                  <div className="modal-meta-value highlight-rose">
                    {selectedMetric.higher_is_better ? "Higher is better" : "Lower is better"}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
