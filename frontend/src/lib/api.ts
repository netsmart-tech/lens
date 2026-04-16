import type {
  ApiErrorBody,
  Activity,
  AuthMe,
  JiraComment,
  JiraIssue,
  JiraIssueDetail,
  ListResponse,
  Tenant,
  Transition,
} from "./types";

/**
 * Base URL for the Lens backend. In dev this is set from
 * NEXT_PUBLIC_API_URL (e.g. http://localhost:8101). In prod the frontend is
 * same-origin with the backend via NGINX, so the env var is empty and /api/*
 * rewrites to the backend service.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;
  constructor(message: string, status: number, body: ApiErrorBody | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    cache: "no-store",
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      body = null;
    }
    const msg = body?.detail || `${res.status} ${res.statusText}`;
    throw new ApiError(typeof msg === "string" ? msg : "Request failed", res.status, body);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // --- Auth ---
  getMe: () => request<AuthMe>("/api/auth/me"),
  loginUrl: () => `${API_BASE}/api/auth/login`,
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),

  // --- Tenants ---
  listTenants: () => request<Tenant[]>("/api/tenants"),

  // --- Jira ---
  listTickets: (tenant: string, params?: { assignee?: "me" | "all" }) => {
    const q = new URLSearchParams();
    if (params?.assignee) q.set("assignee", params.assignee);
    const qs = q.toString() ? `?${q}` : "";
    return request<ListResponse<JiraIssue>>(`/api/${tenant}/tickets${qs}`);
  },
  getTicket: (tenant: string, key: string) =>
    request<JiraIssueDetail>(`/api/${tenant}/tickets/${encodeURIComponent(key)}`),
  refreshTicket: (tenant: string, key: string) =>
    request<JiraIssueDetail>(
      `/api/${tenant}/tickets/${encodeURIComponent(key)}/refresh`,
      { method: "POST" },
    ),
  postComment: (tenant: string, key: string, body: string) =>
    request<JiraComment>(
      `/api/${tenant}/tickets/${encodeURIComponent(key)}/comments`,
      {
        method: "POST",
        body: JSON.stringify({ body }),
      },
    ),
  listTransitions: (tenant: string, key: string) =>
    request<{ transitions: Transition[] }>(
      `/api/${tenant}/tickets/${encodeURIComponent(key)}/transitions`,
    ),
  applyTransition: (tenant: string, key: string, transitionId: string) =>
    request<JiraIssueDetail>(
      `/api/${tenant}/tickets/${encodeURIComponent(key)}/transitions`,
      {
        method: "POST",
        body: JSON.stringify({ transition_id: transitionId }),
      },
    ),

  // --- Activity ---
  listActivity: (tenant: string) =>
    request<ListResponse<Activity>>(`/api/${tenant}/activity`),
};
