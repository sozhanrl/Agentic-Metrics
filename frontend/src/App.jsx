import React, { useEffect, useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import HealthHero from "./components/HealthHero";
import AnomalyPanel from "./components/AnomalyPanel";
import RecommendationCard from "./components/RecommendationCard";
import MetricCard from "./components/MetricCard";
import FeedbackAnalytics from "./components/FeedbackAnalytics";
import WhatIfSimulator from "./components/WhatIfSimulator";
import RootCauseModal from "./components/RootCauseModal";
import AIAssistant from "./components/AIAssistant";
import RiskPredictor from "./components/RiskPredictor";
import TimelineView from "./components/TimelineView";
import TeamInsightsView from "./components/TeamInsightsView";
import ExecutiveDashboard from "./components/ExecutiveDashboard";
import AlertCenter from "./components/AlertCenter";
import CausalGraphVisualizer from "./components/CausalGraphVisualizer";
import ConstraintsPanel from "./components/ConstraintsPanel";
import SystemStatusIndicator from "./components/SystemStatusIndicator";
import ApiErrorState from "./components/ApiErrorState";
import MLIntelligencePanel from "./components/MLIntelligencePanel";
import MetricDetailModal from "./components/MetricDetailModal";
import DatasetMLPanel from "./components/DatasetMLPanel";
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
  const [healthData, setHealthData] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [unreadAlertsCount, setUnreadAlertsCount] = useState(0);
  const [mlPredictions, setMlPredictions] = useState([]);
  const [mlModels, setMlModels] = useState([]);

  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProject, setNewProject] = useState({ name: "", source: "github", external_id: "" });
  const [aiEnabled, setAiEnabled] = useState(false);

  // App views: "project" | "ml" | "dataset_ml" | "executive" | "analytics" | "risks" | "timeline" | "team" | "graph"
  const [appView, setAppView] = useState("project");


  // Filter & Queue tabs states
  const [activeTab, setActiveTab] = useState("open");
  const [searchQuery, setSearchQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("all");

  // Modal dialog states
  const [selectedMetric, setSelectedMetric] = useState(null);
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const [showWhatIf, setShowWhatIf] = useState(false);
  const [rootCauseMetric, setRootCauseMetric] = useState(null);
  const [showAssistant, setShowAssistant] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  const [showConstraints, setShowConstraints] = useState(false);

  // Weight Lens panel
  const [weightLensOpen, setWeightLensOpen] = useState(false);
  const [weightLens, setWeightLens] = useState(null);
  const [weightLensLoading, setWeightLensLoading] = useState(false);

  const loadProjectData = useCallback(async (projectId) => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [metricsData, recsData, historyData, healthRes, anomRes, alertsRes, mlPredsRes, mlModelsRes] = await Promise.all([
        api.getLatestMetrics(projectId),
        api.getRecommendations(projectId),
        api.getAllMetricsHistory(projectId).catch(() => ({})),
        api.getProjectHealth(projectId).catch(() => null),
        api.getAnomalies(projectId).catch(() => []),
        api.getAlerts(projectId, true).catch(() => []),
        api.getMLPredictions(projectId).catch(() => []),
        api.getMLModels().catch(() => []),
      ]);
      setMetrics(metricsData || []);
      setRecommendations(recsData || []);
      setMetricsHistory(historyData || {});
      setHealthData(healthRes);
      setAnomalies(anomRes || []);
      setUnreadAlertsCount(alertsRes?.length || 0);
      setAiEnabled(recsData?.some((r) => r.ai_narrated));
      setMlPredictions(mlPredsRes || []);
      setMlModels(mlModelsRes || []);

    } catch (e) {
      console.error("API error loading project data:", e);
      setError({
        message: e.message || "Failed to load project data",
        status: e.status || "500",
        endpoint: e.endpoint || "/projects",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    api.getProjects().then((data) => {
      setProjects(data);
      if (data.length > 0) setActiveProjectId(data[0].id);
    }).catch((e) => {
      setError({
        message: e.message || "Failed to load projects",
        status: e.status || "500",
        endpoint: e.endpoint || "/projects",
      });
    });
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
      setError({ message: e.message, status: e.status, endpoint: e.endpoint });
    }
  }

  async function handleSeed() {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      await api.seedDemoData(activeProjectId);
      await loadProjectData(activeProjectId);
    } catch (e) {
      setError({ message: e.message, status: e.status, endpoint: e.endpoint });
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
      // Refresh health
      const h = await api.getProjectHealth(activeProjectId);
      setHealthData(h);
    } catch (e) {
      setError({ message: e.message, status: e.status, endpoint: e.endpoint });
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
      setError({ message: e.message, status: e.status, endpoint: e.endpoint });
    }
  }

  async function handleLoadWeightLens() {
    if (!activeProjectId) return;
    setWeightLensLoading(true);
    try {
      const data = await api.getWeightComparison(activeProjectId);
      setWeightLens(data);
    } catch (e) {
      setError({ message: e.message, status: e.status, endpoint: e.endpoint });
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

  const getTabCount = (status) => {
    return recommendations.filter((r) => r.status === status).length;
  };

  const filteredRecs = recommendations.filter((rec) => {
    const matchesStatus =
      activeTab === "open"
        ? rec.status === "open" || rec.status === "in_progress"
        : rec.status === activeTab;

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

    const pathD = points.reduce((acc, p, i) => {
      const x = getX(i);
      const y = getY(p.value);
      return acc + `${i === 0 ? "M" : "L"} ${x} ${y}`;
    }, "");

    const targetY = targetVal !== undefined ? getY(targetVal) : null;
    const chartColor = "var(--teal)";

    return (
      <div className="modal-chart-svg-container">
        <svg className="modal-chart-svg" viewBox={`0 0 ${width} ${height}`}>
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

          {targetY !== null && (
            <g>
              <line
                className="chart-target-line"
                x1={paddingX}
                y1={targetY}
                x2={width - paddingX}
                y2={targetY}
                stroke="var(--amber)"
                opacity="0.6"
              />
              <text
                x={width - paddingX - 10}
                y={targetY - 6}
                fill="var(--amber)"
                fontSize="10"
                fontFamily="var(--font-mono)"
                textAnchor="end"
              >
                Target: {targetVal} {metric.unit}
              </text>
            </g>
          )}

          <path className="chart-line-glow" d={pathD} stroke={chartColor} />
          <path className="chart-line" d={pathD} stroke={chartColor} />

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
        appView={appView}
        onSelectView={setAppView}
        unreadAlertsCount={unreadAlertsCount}
        onOpenAlerts={() => setShowAlerts(true)}
        onOpenAssistant={() => setShowAssistant(true)}
      />

      <main className="main-panel">
        <header className="top-bar">
          <div className="top-title-block">
            <h1 className="page-title">
              {appView === "analytics"
                ? "Feedback Analytics"
                : appView === "executive"
                ? "Executive Overview"
                : appView === "risks"
                ? "Predictive Risk Intelligence"
                : appView === "timeline"
                ? "Event Timeline"
                : appView === "team"
                ? "Engineering Team Insights"
                : appView === "graph"
                ? "Self-Evolving Causal Graph"
                : appView === "dataset_ml"
                ? "Dataset ML Intelligence"
                : projects.find((p) => p.id === activeProjectId)?.name || "AI Engineering Platform"}
            </h1>
            <p className="page-subtitle">
              {projects.find((p) => p.id === activeProjectId)?.external_id || "Evidence-Adaptive Multi-Agent Intelligence"}
            </p>
          </div>

          <div className="top-actions">
            <SystemStatusIndicator />
            <button className="btn ghost" onClick={() => setShowNewProject((s) => !s)}>
              + New project
            </button>
            <button className="btn secondary" onClick={() => setShowWhatIf(true)} disabled={!activeProjectId}>
              🎛️ What-If
            </button>
            <button className="btn secondary" onClick={() => setShowConstraints(true)} disabled={!activeProjectId}>
              🎯 Goal Optimizer
            </button>
            <button className="btn secondary" onClick={handleSeed} disabled={!activeProjectId || loading}>
              Seed demo data
            </button>
            <button className="btn primary" onClick={handleGenerate} disabled={!activeProjectId || generating}>
              {generating ? "Reasoning & Arbitrating…" : "⚡ Run Agent Pipeline"}
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
              placeholder="Repository URL / Server identifier"
              value={newProject.external_id}
              onChange={(e) => setNewProject({ ...newProject, external_id: e.target.value })}
              style={{ flex: 1, minWidth: 280 }}
              required
            />
            <button type="submit" className="btn primary">Create</button>
          </form>
        )}

        {error && typeof error === "object" && (
          <ApiErrorState
            title="Intelligence Pipeline Request Exception"
            message={error.message}
            endpoint={error.endpoint}
            status={error.status}
            errorDetails={error.message}
            onRetry={() => loadProjectData(activeProjectId)}
          />
        )}

        {/* View Routing */}
        {appView === "ml" && (
          <MLIntelligencePanel
            projectId={activeProjectId}
            projects={projects}
          />
        )}
        {appView === "dataset_ml" && (
          <DatasetMLPanel
            projectId={activeProjectId}
          />
        )}
        {appView === "analytics" && <FeedbackAnalytics />}
        {appView === "executive" && (
          <ExecutiveDashboard
            health={healthData}
            recommendations={recommendations}
            anomalies={anomalies}
            metrics={metrics}
            loading={loading}
            error={error}
            onRetry={() => loadProjectData(activeProjectId)}
            onOpenRootCause={(key) => setRootCauseMetric(key)}
            onStartAction={(recId) => handleStatusChange(recId, "in_progress")}
          />
        )}
        {appView === "risks" && <RiskPredictor projectId={activeProjectId} />}
        {appView === "timeline" && <TimelineView projectId={activeProjectId} />}
        {appView === "team" && <TeamInsightsView projectId={activeProjectId} />}
        {appView === "graph" && (
          <CausalGraphVisualizer
            projectId={activeProjectId}
            metrics={metrics}
            recommendations={recommendations}
          />
        )}


        {/* Main Dashboard View */}
        {appView === "project" && activeProjectId && (
          <>
            {/* 1. Health Hero */}
            <HealthHero
              health={healthData}
              onOpenWhatIf={() => setShowWhatIf(true)}
              onOpenRisks={() => setAppView("risks")}
            />

            {/* 2. Anomaly Detection Panel */}
            <AnomalyPanel
              anomalies={anomalies}
              onAcknowledge={(id) =>
                setAnomalies((prev) =>
                  prev.map((a) => (a.id === id ? { ...a, is_acknowledged: true } : a))
                )
              }
              onInvestigateRootCause={(key) => setRootCauseMetric(key)}
            />

            {/* 3. Weight Lens Panel */}
            <div className="weight-lens">
              <div
                className={`weight-lens-header ${weightLensOpen ? "open" : ""}`}
                onClick={handleToggleWeightLens}
              >
                <div className="weight-lens-title">
                  <span className="weight-lens-icon">⚖️</span>
                  Evidence-Adaptive Arbitration & Weight Lens
                  <span className="weight-lens-subtitle">Prior → Bayesian Self-Learned → Adaptive Context</span>
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

              {weightLensOpen && weightLens && (
                <div className="weight-lens-body">
                  <table className="weight-table">
                    <thead>
                      <tr>
                        <th>Category</th>
                        <th>Base Prior</th>
                        <th>Self-Learned</th>
                        <th>Adaptive Context</th>
                        <th>Effective Weight</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.keys(weightLens.base_prior || {}).map((cat) => (
                        <tr key={cat}>
                          <td className={`wt-category ${cat}`}>{CATEGORY_LABELS[cat] || cat}</td>
                          <td className="wt-value">{weightLens.base_prior[cat]?.toFixed(3)}</td>
                          <td className="wt-value">{weightLens.self_learned[cat]?.toFixed(3)}</td>
                          <td className="wt-value">{weightLens.adaptive_context[cat]?.toFixed(3)}</td>
                          <td className="wt-effective">{weightLens.effective[cat]?.toFixed(3)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 4. Priority Queue & Metrics Panel Grid */}
            <div className="content-grid">
              <section className="priority-queue">
                <div className="section-heading">
                  <h2>Prioritized AI Action Recommendations</h2>
                  <span className="section-caption">Evidence-adaptive, causal-discounted suggestions</span>
                </div>

                <div className="queue-controls">
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Search action plans, problems, root causes..."
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

                <div className="tab-strip">
                  <button
                    className={`tab-btn ${activeTab === "open" ? "active" : ""}`}
                    onClick={() => setActiveTab("open")}
                  >
                    Active / In Progress <span className="tab-badge">{getTabCount("open") + getTabCount("in_progress")}</span>
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
                    <p>No recommendations match your current filter.</p>
                  </div>
                )}

                <div className="rec-list">
                  {filteredRecs.map((rec, i) => (
                    <RecommendationCard
                      key={rec.id}
                      recommendation={rec}
                      rank={i + 1}
                      onStatusChange={handleStatusChange}
                      onOpenRootCause={(key) => setRootCauseMetric(key)}
                    />
                  ))}
                </div>
              </section>

              <section className="metrics-panel">
                <div className="section-heading">
                  <h2>Observed Metrics Panel</h2>
                  <span className="section-caption">Click a card for time-series chart & root cause</span>
                </div>

                {Object.entries(metricsByCategory).map(([category, list]) => (
                  <div key={category} className="metric-category" data-category={category}>
                    <div className="metric-category-label">
                      {CATEGORY_LABELS[category] || category}
                    </div>
                    <div className="metric-grid">
                      {list.map((m) => {
                        const pred = mlPredictions.find(
                          (p) => p.target_metric === m.metric_key || p.category === m.category
                        );
                        return (
                          <MetricCard
                            key={m.id}
                            metric={m}
                            history={metricsHistory[m.metric_id] || []}
                            prediction={pred}
                            onClick={() => setSelectedMetric(m)}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))}
              </section>
            </div>
          </>
        )}
      </main>

      {/* Metric Detail Modal with ML Forecasts & Explainability */}
      {selectedMetric && (
        <MetricDetailModal
          metric={selectedMetric}
          history={metricsHistory[selectedMetric.metric_id] || []}
          prediction={mlPredictions.find(
            (p) => p.target_metric === selectedMetric.metric_key || p.category === selectedMetric.category
          )}
          modelInfo={mlModels.find((m) => m.category === selectedMetric.category)}
          onClose={() => setSelectedMetric(null)}
          onOpenRootCause={(key) => setRootCauseMetric(key)}
        />
      )}

      {/* Modals & Slide-outs */}
      {showWhatIf && (

        <WhatIfSimulator
          projectId={activeProjectId}
          metrics={metrics}
          onClose={() => setShowWhatIf(false)}
        />
      )}

      {rootCauseMetric && (
        <RootCauseModal
          projectId={activeProjectId}
          metricKey={rootCauseMetric}
          onClose={() => setRootCauseMetric(null)}
        />
      )}

      {showAssistant && (
        <AIAssistant
          projectId={activeProjectId}
          onClose={() => setShowAssistant(false)}
        />
      )}

      {showAlerts && (
        <AlertCenter
          projectId={activeProjectId}
          onClose={() => setShowAlerts(false)}
        />
      )}

      {showConstraints && (
        <ConstraintsPanel
          projectId={activeProjectId}
          onClose={() => setShowConstraints(false)}
        />
      )}
    </div>
  );
}
