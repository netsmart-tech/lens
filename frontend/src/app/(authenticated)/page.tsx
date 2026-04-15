"use client";

import Link from "next/link";
import { Building2, Eye } from "lucide-react";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { TopNav } from "@/components/top-nav";
import { TenantProvider } from "@/lib/tenant-context";
import { useAuth } from "@/lib/auth-context";

/**
 * Tenant selector landing. The top nav is rendered with an empty
 * TenantProvider (no slug) so the "Select tenant" pill/search opens the
 * cmdk palette from this page too.
 */
export default function TenantSelectorPage() {
  const { tenants, user } = useAuth();

  return (
    <TenantProvider slug="">
      <div className="min-h-screen flex flex-col">
        <TopNav />
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
          <header className="mb-8">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Eye className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">
                  Welcome{user ? `, ${user.display_name.split(" ")[0]}` : ""}.
                </h1>
                <p className="text-sm text-muted-foreground">
                  Select a client to see their tickets, activity, and reports.
                </p>
              </div>
            </div>
          </header>

          {tenants.length === 0 ? (
            <EmptyState
              icon={Building2}
              title="No tenants yet"
              description="You haven't been granted access to any clients. Contact your administrator to get added."
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {tenants.map((t) => (
                <Link key={t.slug} href={`/${t.slug}`} className="group">
                  <Card className="transition-colors group-hover:border-foreground/20 group-hover:shadow">
                    <CardHeader>
                      <div className="mb-3 flex items-center justify-between">
                        <span
                          className="h-8 w-8 rounded-md border"
                          style={{ backgroundColor: t.color_hex }}
                          aria-hidden
                        />
                        <span className="text-xs text-muted-foreground uppercase tracking-wider">
                          {t.role}
                        </span>
                      </div>
                      <CardTitle className="text-lg">{t.name}</CardTitle>
                      <CardDescription>/{t.slug}</CardDescription>
                    </CardHeader>
                  </Card>
                </Link>
              ))}
            </div>
          )}

          <p className="mt-10 text-xs text-muted-foreground">
            Tip: press{" "}
            <kbd className="rounded border bg-muted px-1 font-mono">⌘K</kbd>{" "}
            anywhere to switch clients or jump to a page.
          </p>
        </main>
      </div>
    </TenantProvider>
  );
}
