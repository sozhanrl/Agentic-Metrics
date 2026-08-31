const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const errorMsg = body.detail || `HTTP Error ${res.status}: ${res.statusText}`;
      const err = new Error(errorMsg);
      err.status = res.status;
      err.endpoint = `${BASE_URL}${path}`;
      throw err;
    }
    return await res.json();
  } catch (err) {
    if (!err.endpoint) {
      err.endpoint = `${BASE_URL}${path}`;
      err.status = "FETCH_FAILED";
      err.message = err.message || "Unable to reach backend service. Check connection.";
    }
    throw err;
  }
}

export const api = {
  // ---- System ----
  getSystemHealth: () => request("/health"),

  // ---- Projects ----
  getProjects: () => request("/projects"),
  getProject: (projectId) => request(`/projects/${projectId}`),
  createProject: (project) =>
    request("/projects", { method: "POST", body: JSON.stringify(project) }),


  // ---- Metrics ----
  getLatestMetrics: (projectId) => request(`/metrics/latest/${projectId}`),
  getAllMetricsHistory: (projectId) => request(`/metrics/history-all/${projectId}`),
  getMetricHistory: (projectId, metricId) => request(`/metrics/history/${projectId}/${metricId}`),

  // ---- Recommendations & Lifecycle ----
  getRecommendations: (projectId, status) =>
    request(`/recommendations/${projectId}${status ? `?status=${status}` : ""}`),
  generateRecommendations: (projectId) =>
    request(`/recommendations/${projectId}/generate`, { method: "POST" }),
  updateRecommendationStatus: (id, status) =>
    request(`/recommendations/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  startRecommendation: (id, notes) =>
    request(`/recommendations/${id}/start`, {
      method: "POST",
      body: JSON.stringify({ action_type: "start", notes }),
    }),
  resolveRecommendation: (id, notes) =>
    request(`/recommendations/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ action_type: "resolve", notes }),
    }),
  verifyRecommendation: (id) =>
    request(`/recommendations/${id}/verify`, { method: "POST" }),
  getRecommendationOutcome: (id) =>
    request(`/recommendations/${id}/outcome`),
  optimizeRecommendations: (projectId, constraints) =>
    request(`/recommendations/${projectId}/optimize`, {
      method: "POST",
      body: JSON.stringify(constraints || []),
    }),

  // ---- Feedback ----
  submitFeedback: (payload) =>
    request("/feedback", { method: "POST", body: JSON.stringify(payload) }),

  // ---- Health Score ----
  getProjectHealth: (projectId) => request(`/projects/${projectId}/health`),
  getHealthHistory: (projectId) => request(`/projects/${projectId}/health/history`),

  // ---- Anomalies ----
  getAnomalies: (projectId) => request(`/projects/${projectId}/anomalies`),
  acknowledgeAnomaly: (anomalyId) =>
    request(`/projects/anomalies/${anomalyId}/acknowledge`, { method: "POST" }),

  // ---- Analysis & Simulation ----
  getRootCause: (projectId, metricKey) =>
    request(`/projects/${projectId}/root-cause/${metricKey}`),
  simulateWhatIf: (projectId, simulatedValues) =>
    request(`/projects/${projectId}/what-if`, {
      method: "POST",
      body: JSON.stringify({ simulated_values: simulatedValues }),
    }),

  // ---- Risks & Timeline ----
  getProjectRisks: (projectId) => request(`/projects/${projectId}/risks`),
  getTimeline: (projectId, eventType) =>
    request(`/projects/${projectId}/timeline${eventType ? `?event_type=${eventType}` : ""}`),

  // ---- AI Assistant ----
  askAssistant: (projectId, question) =>
    request(`/projects/${projectId}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  // ---- Alerts ----
  getAlerts: (projectId, unreadOnly = false) =>
    request(`/projects/${projectId}/alerts${unreadOnly ? "?unread_only=true" : ""}`),
  markAlertRead: (alertId) =>
    request(`/projects/alerts/${alertId}/read`, { method: "POST" }),

  // ---- Insights & Telemetry ----
  getTeamInsights: (projectId) => request(`/projects/${projectId}/team-insights`),
  getGitHubInsights: (projectId) => request(`/projects/${projectId}/github`),

  // ---- Causal Graph & Self-Learning ----
  getCausalGraph: (projectId) => request(`/admin/causal-graph/${projectId}`),
  evolveCausalGraph: (projectId) =>
    request(`/admin/evolve-graph/${projectId}`, { method: "POST" }),
  triggerSelfLearning: (projectId) =>
    request(`/admin/self-learn/${projectId}`, { method: "POST" }),
  getLearningStrategy: (projectId) => request(`/admin/learning-strategy/${projectId}`),

  // ---- Dev / Seed ----
  seedDemoData: (projectId) =>
    request(`/dev/seed/${projectId}`, { method: "POST" }),
  getWeightComparison: (projectId) =>
    request(`/admin/weights/compare/${projectId}`),

  // ---- Feedback Analytics ----
  getFeedbackFilters: () => request("/analytics/feedback/filters"),
  getFeedbackSummary: ({ projectId, category, userRole } = {}) => {
    const params = new URLSearchParams();
    if (projectId != null) params.set("project_id", projectId);
    if (category) params.set("category", category);
    if (userRole) params.set("user_role", userRole);
    const qs = params.toString();
    return request(`/analytics/feedback/summary${qs ? "?" + qs : ""}`);
  },
  getFeedbackRows: ({ projectId, category, userRole } = {}) => {
    const params = new URLSearchParams();
    if (projectId != null) params.set("project_id", projectId);
    if (category) params.set("category", category);
    if (userRole) params.set("user_role", userRole);
    const qs = params.toString();
    return request(`/analytics/feedback/rows${qs ? "?" + qs : ""}`);
  },
};
