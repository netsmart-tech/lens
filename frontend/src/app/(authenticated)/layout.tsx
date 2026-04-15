"use client";

import { AuthProvider } from "@/lib/auth-context";

/**
 * Auth boundary for every `/[tenant]/...` and the tenant-selector landing.
 * The AuthProvider calls /api/auth/me on mount, renders a loading spinner
 * while it resolves, and redirects to /login on 401.
 *
 * The top nav is rendered inside each inner layout (root tenant selector +
 * per-tenant layout) so it can access TenantContext.
 */
export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthProvider>{children}</AuthProvider>;
}
