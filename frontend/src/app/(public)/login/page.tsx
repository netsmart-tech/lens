"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await api.getMe();
        if (!cancelled) router.replace("/");
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 401) {
          // Surface non-auth errors via console; still drop to login UI.
          console.warn("Auth probe failed:", err);
        }
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
            <Eye className="h-7 w-7 text-primary" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Lens</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Netsmart client portal
          </p>
        </div>

        <Button asChild size="lg" className="w-full">
          <a href={api.loginUrl()}>Sign in with Netsmart</a>
        </Button>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Access is managed through Authentik. Contact Steve for an invitation.
        </p>
      </div>
    </div>
  );
}
