const API_ROOT = "/api";

export async function api(path, options = {}) {
  const config = { ...options, headers: { ...(options.headers || {}) } };
  if (config.body && !(config.body instanceof FormData)) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(config.body);
  }
  const response = await fetch(`${API_ROOT}${path}`, config);
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data?.detail || Object.values(data || {}).flat().join(" ") || `Ошибка ${response.status}`;
    throw new Error(message);
  }
  return data;
}

export function rows(data) {
  return Array.isArray(data) ? data : data?.results || [];
}

export function query(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  const string = search.toString();
  return string ? `?${string}` : "";
}

