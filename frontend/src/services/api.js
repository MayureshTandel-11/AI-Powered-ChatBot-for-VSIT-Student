// Empty string is intentional for Docker/nginx same-origin proxying.
const API_BASE =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : "http://127.0.0.1:8000";

const TOKEN_KEY = "access_token";
const USER_KEY = "user";

function getHeaders(includeAuth = true) {
  const headers = { "Content-Type": "application/json" };
  if (includeAuth) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }
  return headers;
}

async function handleResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(", ")
      : detail || data.message || "Request failed";
    throw new Error(message);
  }
  return data;
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function saveAuth(tokenResponse) {
  localStorage.setItem(TOKEN_KEY, tokenResponse.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(tokenResponse.user));
}

export async function register(payload) {
  const response = await fetch(`${API_BASE}/api/auth/register`, {
    method: "POST",
    headers: getHeaders(false),
    body: JSON.stringify(payload),
  });
  const data = await handleResponse(response);
  saveAuth(data);
  return data;
}

export async function login(email, password) {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: getHeaders(false),
    body: JSON.stringify({ email, password }),
  });
  const data = await handleResponse(response);
  saveAuth(data);
  return data;
}

export async function getMe() {
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    headers: getHeaders(true),
  });
  return handleResponse(response);
}

export function logout() {
  clearAuth();
}

export async function checkHealth() {
  const response = await fetch(`${API_BASE}/health`);
  return handleResponse(response);
}

export async function sendChatMessage(message, sessionId = null) {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: getHeaders(true),
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  });
  return handleResponse(response);
}

export async function createChatSession() {
  const response = await fetch(`${API_BASE}/api/chat/session`, {
    method: "POST",
    headers: getHeaders(true),
  });
  return handleResponse(response);
}

export async function getChatHistory() {
  const response = await fetch(`${API_BASE}/api/chat/history`, {
    headers: getHeaders(true),
  });
  return handleResponse(response);
}

export async function getChatSession(sessionId) {
  const response = await fetch(`${API_BASE}/api/chat/${sessionId}`, {
    headers: getHeaders(true),
  });
  return handleResponse(response);
}

function getAuthHeaders() {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getAdminStatistics() {
  const response = await fetch(`${API_BASE}/api/admin/statistics`, {
    headers: getHeaders(true),
  });
  return handleResponse(response);
}

export async function getAdminDocuments() {
  const response = await fetch(`${API_BASE}/api/admin/documents`, {
    headers: getHeaders(true),
  });
  return handleResponse(response);
}

export async function uploadAdminDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/api/admin/documents/upload`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });
  return handleResponse(response);
}

export async function deleteAdminDocument(documentId) {
  const response = await fetch(`${API_BASE}/api/admin/documents/${documentId}`, {
    method: "DELETE",
    headers: getHeaders(true),
  });
  return handleResponse(response);
}

export async function reindexAdminDocuments() {
  const response = await fetch(`${API_BASE}/api/admin/documents/reindex`, {
    method: "POST",
    headers: getHeaders(true),
  });
  return handleResponse(response);
}

export async function getAdminMlMetrics() {
  const response = await fetch(`${API_BASE}/api/admin/ml-metrics`, {
    headers: getHeaders(true),
  });
  return handleResponse(response);
}
