/**
 * Phase 1 hand-written types. These get replaced by `api-types.ts` generated
 * via `npm run gen:api` once Teo's `make openapi` target lands. Kept small
 * and focused on the list/detail responses the MVP renders.
 */

// --- Auth ---

export interface User {
  id: string;
  email: string;
  display_name: string;
  authentik_sub: string | null;
}

export type TenantRole = "owner" | "viewer";

export interface Tenant {
  id: string;
  slug: string;
  name: string;
  color_hex: string;
  logo_ref: string | null;
  role: TenantRole;
}

export interface AuthMe {
  user: User;
  tenants: Tenant[];
}

// --- Sync envelope (DESIGN §3.7) ---

export type SyncState =
  | "never-synced"
  | "syncing-first-pass"
  | "synced-but-empty"
  | "stale"
  | "fresh"
  | "failed";

export interface SyncEnvelope {
  state: SyncState;
  last_run_at: string | null;
  last_cursor_at: string | null;
  last_error: string | null;
  progress: { pct: number } | null;
}

export interface ListResponse<T> {
  items: T[];
  sync: SyncEnvelope;
}

// --- Jira ---

export interface JiraIssue {
  site_id: string;
  key: string;
  summary: string;
  status: string | null;
  priority: string | null;
  assignee: string | null;
  reporter: string | null;
  created: string | null;
  updated: string | null;
}

export interface JiraComment {
  id: number;
  author: string;
  body: string;
  created: string;
}

export interface JiraIssueDetail extends JiraIssue {
  description: string | null;
  comments: JiraComment[];
}

// --- Activity ---

export interface Activity {
  id: number;
  source: string;
  actor: string;
  action: string;
  subject: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
}

// --- API error ---

export interface ApiErrorBody {
  detail?: string;
  [k: string]: unknown;
}
