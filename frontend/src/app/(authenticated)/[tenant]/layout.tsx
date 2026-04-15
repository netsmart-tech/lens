"use client";

import { use } from "react";
import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TopNav } from "@/components/top-nav";
import { TenantProvider } from "@/lib/tenant-context";
import { useAuth } from "@/lib/auth-context";

export default function TenantLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ tenant: string }>;
}) {
  const { tenant: slug } = use(params);
  const { tenants } = useAuth();
  const tenant = tenants.find((t) => t.slug === slug) ?? null;

  if (!tenant) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-4 text-center">
        <ShieldAlert className="h-10 w-10 text-muted-foreground" />
        <div>
          <h1 className="text-lg font-semibold">Tenant not found</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            You don&apos;t have access to <code>/{slug}</code>, or it doesn&apos;t exist.
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href="/">Back to tenant selector</Link>
        </Button>
      </div>
    );
  }

  // Set the tenant accent CSS variable on the subtree. This is the one place
  // the tenant color influences the UI; background/foreground stay app-owned.
  return (
    <TenantProvider slug={slug}>
      <div
        className="min-h-screen flex flex-col"
        style={
          {
            ["--lens-tenant-accent" as string]: tenant.color_hex,
          } as React.CSSProperties
        }
      >
        <TopNav />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
          {children}
        </main>
      </div>
    </TenantProvider>
  );
}
