const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  getProjects: () => request("/projects"),
  createProject: (project) =>
    request("/projects", { method: "POST", body: JSON.stringify(project) }),

  getLatestMetrics: (projectId) => request(`/metrics/latest/${projectId}`),
  getAllMetricsHistory: (projectId) => request(`/metrics/history-all/${projectId}`),

  getRecommendations: (projectId) => request(`/recommendations/${projectId}`),
  generateRecommendations: (projectId) =>
    request(`/recommendations/${projectId}/generate`, { method: "POST" }),
  updateRecommendationStatus: (id, status) =>
    request(`/recommendations/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  submitFeedback: (payload) =>
    request("/feedback", { method: "POST", body: JSON.stringify(payload) }),

  seedDemoData: (projectId) =>
    request(`/dev/seed/${projectId}`, { method: "POST" }),
};
