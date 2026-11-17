import axios from "axios";

export const API_BASE = (import.meta.env.VITE_API_BASE || "/api").replace(/\/$/, "");

const TOKEN_STORAGE_KEY = "nexus.auth.token";
const USER_STORAGE_KEY = "nexus.auth.user";

export function getStoredToken(): string {
  return localStorage.getItem(TOKEN_STORAGE_KEY) || "";
}

export function setStoredToken(token: string): void {
  if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function getStoredUser(): unknown {
  const raw = localStorage.getItem(USER_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setStoredUser(user: unknown): void {
  if (user) localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_STORAGE_KEY);
}

export function apiUrl(path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  if (API_BASE.startsWith("http")) return `${API_BASE}${clean}`;
  return `${API_BASE}${clean}`;
}

/**
 * Server payloads contain absolute API paths (e.g. /api/chat/files/x/download/).
 * Axios already has API_BASE configured, so strip that prefix before re-using
 * such a URL on the instance.
 */
export function requestPath(url: string): string {
  if (/^https?:\/\//.test(url)) return url;
  if (API_BASE && url.startsWith(`${API_BASE}/`)) {
    return url.slice(API_BASE.length) || "/";
  }
  return url;
}

export function websocketUrl(path: string): string {
  const explicit = import.meta.env.VITE_WS_BASE as string | undefined;
  if (explicit) return `${explicit.replace(/\/$/, "")}${path}`;
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${location.host}${path}`;
}

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token && !config.headers.has("Authorization")) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

let redirectingAfterRevocation = false;

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const requestUrl = String(error.config?.url || "");
      const requestToken = error.config?.headers?.get("Authorization");
      if (
        error.response?.status === 401 &&
        !requestUrl.includes("/auth/login/") &&
        !requestUrl.includes("/auth/logout/") &&
        requestToken === `Token ${getStoredToken()}`
      ) {
        setStoredToken("");
        setStoredUser(null);
        if (!redirectingAfterRevocation && location.pathname !== "/") {
          redirectingAfterRevocation = true;
          const redirect = `${location.pathname}${location.search}${location.hash}`;
          location.assign(`/?redirect=${encodeURIComponent(redirect)}`);
        }
      }
    }
    return Promise.reject(error);
  },
);

export function bearerHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = getStoredToken();
  if (token) headers.Authorization = `Token ${token}`;
  return headers;
}

export function extractApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (data) {
      const detail = data.detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail.map(String).join("；");
      }
      const nonField = data.non_field_errors;
      if (Array.isArray(nonField)) return nonField.map(String).join("；");
      for (const value of Object.values(data)) {
        if (typeof value === "string") return value;
        if (Array.isArray(value) && value.length && value.every((item) => typeof item === "string")) {
          return value.join("；");
        }
      }
    }
    if (error.response?.status === 401) return "登录已失效，请重新登录。";
    if (error.response?.status === 403) return "当前账号没有执行此操作的权限。";
    if (error.code === "ECONNABORTED") return "请求超时，请稍后再试。";
    if (!error.response) return "无法连接到后端服务，请确认服务已启动。";
  }
  if (error instanceof Error) return error.message;
  return "请求失败，请稍后再试。";
}

export async function fetchBlob(url: string, params?: Record<string, unknown>): Promise<Blob> {
  const response = await api.get(requestPath(url), {
    responseType: "blob",
    params,
  });
  return response.data as Blob;
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(href), 2000);
}

export default api;
