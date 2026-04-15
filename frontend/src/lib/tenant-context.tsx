"use client";

import { createContext, useContext, useMemo } from "react";
import { useAuth } from "./auth-context";
import type { Tenant } from "./types";

interface TenantContextValue {
  tenant: Tenant | null;
}

const TenantContext = createContext<TenantContextValue>({ tenant: null });

/**
 * Resolve the current tenant by slug from the route param, looked up against
 * the authenticated user's tenant list. If the slug isn't in the user's
 * list, `tenant` is null and the layout should render a 403.
 */
export function TenantProvider({
  slug,
  children,
}: {
  slug: string;
  children: React.ReactNode;
}) {
  const { tenants } = useAuth();
  const tenant = useMemo(
    () => tenants.find((t) => t.slug === slug) ?? null,
    [tenants, slug],
  );
  return (
    <TenantContext.Provider value={{ tenant }}>
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant(): Tenant {
  const { tenant } = useContext(TenantContext);
  if (!tenant) {
    throw new Error("useTenant() called outside of a resolved TenantProvider");
  }
  return tenant;
}

export function useTenantOrNull(): Tenant | null {
  return useContext(TenantContext).tenant;
}
