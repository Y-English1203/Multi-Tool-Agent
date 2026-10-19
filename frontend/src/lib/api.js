const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function buildQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function request(path, { method = "GET", body, headers = {}, signal } = {}) {
  const options = {
    method,
    headers: { ...headers },
    signal,
  };

  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${BASE}${path}`, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("无法连接后端服务，请确认 FastAPI 已在 127.0.0.1:8000 启动。", {
      cause: error,
    });
  }

  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    let detail = data?.detail ?? data?.error ?? `请求失败（HTTP ${response.status}）`;
    if (Array.isArray(detail)) {
      detail = detail.map((item) => item.msg || JSON.stringify(item)).join("；");
    }
    const error = new Error(String(detail));
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export const api = {
  health: () => request("/api/health"),

  dashboard: () => request("/api/dashboard"),
  overview: (params) => request(`/api/analytics/overview${buildQuery(params)}`),
  trend: (params) => request(`/api/analytics/trend${buildQuery(params)}`),
  categories: (params) => request(`/api/analytics/categories${buildQuery(params)}`),
  topProducts: (params) => request(`/api/analytics/top-products${buildQuery(params)}`),
  cities: (params) => request(`/api/analytics/cities${buildQuery(params)}`),
  departments: (params) => request(`/api/analytics/departments${buildQuery(params)}`),
  orderStatus: () => request("/api/analytics/order-status"),
  channels: () => request("/api/analytics/channels"),
  orders: (params) => request(`/api/orders${buildQuery(params)}`),
  products: (params) => request(`/api/products${buildQuery(params)}`),
  filters: () => request("/api/filters"),

  sqlQuery: (question) =>
    request("/api/sql/query", { method: "POST", body: { question } }),

  knowledgeStats: () => request("/api/knowledge/stats"),
  knowledgeDocuments: () => request("/api/knowledge/documents"),
  knowledgeSearch: (q, topK = 5) =>
    request(`/api/knowledge/search${buildQuery({ q, top_k: topK })}`),
  uploadKnowledge: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/knowledge/documents", { method: "POST", body: form });
  },
  deleteKnowledge: (docId) =>
    request(`/api/knowledge/documents/${encodeURIComponent(docId)}`, {
      method: "DELETE",
    }),
  rebuildKnowledge: () => request("/api/knowledge/rebuild", { method: "POST" }),

  ticketMeta: () => request("/api/tickets/meta"),
  ticketStats: (userId) => request(`/api/tickets/stats${buildQuery({ user_id: userId })}`),
  tickets: (params) => request(`/api/tickets${buildQuery(params)}`),
  ticket: (id, userId) =>
    request(`/api/tickets/${id}${buildQuery({ user_id: userId })}`),
  createTicket: (payload) =>
    request("/api/tickets", { method: "POST", body: payload }),
  updateTicket: (id, payload) =>
    request(`/api/tickets/${id}`, { method: "PATCH", body: payload }),

  sessions: (userId) => request(`/api/sessions${buildQuery({ user_id: userId })}`),
  sessionMessages: (sessionId, userId) =>
    request(
      `/api/sessions/${encodeURIComponent(sessionId)}/messages${buildQuery({
        user_id: userId,
      })}`
    ),
  deleteSession: (sessionId, userId) =>
    request(
      `/api/sessions/${encodeURIComponent(sessionId)}${buildQuery({
        user_id: userId,
      })}`,
      { method: "DELETE" }
    ),
  clearConversations: (userId) =>
    request(`/api/conversations${buildQuery({ user_id: userId })}`, {
      method: "DELETE",
    }),
  conversationStats: (userId) =>
    request(`/api/conversations/stats${buildQuery({ user_id: userId })}`),

  ask: (payload, signal) =>
    request("/ask/supervisor", { method: "POST", body: payload, signal }),
};

export { BASE as API_BASE };
