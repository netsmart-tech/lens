"use client";

/**
 * Hand-rolled OIDC session context. Same shape as secrets-proxy.
 *
 * Backend owns the OIDC flow (Authentik authorization-code + PKCE). The
 * browser only sees an HTTP-only session cookie. We hit /api/auth/me with
 * credentials:"include" to hydrate {user, tenants}; on 401 we bounce to
 * /login. When LENS_DEV_AUTH=1 is set on the backend, /api/auth/me returns
 * Steve's session immediately (no redirect).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "./api";
import type { AuthMe, Tenant, User } from "./types";

interface AuthContextValue {
  user: User | null;
  tenants: Tenant[];
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  tenants: [],
  loading: true,
  refresh: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthMe | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refresh = useCallback(async () => {
    try {
      const me = await api.getMe();
      setState(me);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setState(null);
        router.replace("/login");
      } else {
        // Network error — surface via loading=false, let consumers show error UI
        setState(null);
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* ignore */
    }
    setState(null);
    router.replace("/login");
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-muted-foreground">Loading Lens…</p>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider
      value={{
        user: state?.user ?? null,
        tenants: state?.tenants ?? [],
        loading,
        refresh,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
