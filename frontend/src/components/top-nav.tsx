"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { LogOut, Search } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { TenantPill } from "@/components/tenant-pill";
import { TenantSwitcher } from "@/components/tenant-switcher";
import { useAuth } from "@/lib/auth-context";
import { useTenantOrNull } from "@/lib/tenant-context";
import { cn } from "@/lib/utils";

interface NavLink {
  href: string;
  label: string;
}

function tenantLinks(slug: string): NavLink[] {
  return [
    { href: `/${slug}`, label: "Home" },
    { href: `/${slug}/tickets`, label: "Tickets" },
    { href: `/${slug}/activity`, label: "Activity" },
    { href: `/${slug}/reports`, label: "Reports" },
    { href: `/${slug}/settings`, label: "Settings" },
  ];
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function TopNav() {
  const { user, logout } = useAuth();
  const tenant = useTenantOrNull();
  const pathname = usePathname();
  const [paletteOpen, setPaletteOpen] = useState(false);

  const links = tenant ? tenantLinks(tenant.slug) : [];

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
        <Link
          href="/"
          className="flex items-center gap-2 text-sm font-semibold tracking-tight"
        >
          <span
            className="inline-block h-5 w-5 rounded-sm bg-primary"
            aria-hidden
          />
          Lens
        </Link>

        {tenant ? (
          <TenantPill
            tenant={tenant}
            onClick={() => setPaletteOpen(true)}
          />
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPaletteOpen(true)}
            className="gap-2"
          >
            <Search className="h-3.5 w-3.5" />
            Select tenant
            <kbd className="ml-1 rounded border bg-muted px-1 font-mono text-[10px]">
              ⌘K
            </kbd>
          </Button>
        )}

        {tenant && (
          <nav
            aria-label="Tenant navigation"
            className="hidden items-center gap-1 md:flex"
          >
            {links.map((l) => {
              const active =
                l.href === `/${tenant.slug}`
                  ? pathname === l.href
                  : pathname.startsWith(l.href);
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={cn(
                    "relative rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground",
                    active && "text-foreground",
                  )}
                >
                  {l.label}
                  {active && (
                    <span
                      className="absolute inset-x-2 -bottom-[9px] h-0.5 rounded-full"
                      style={{
                        backgroundColor: "var(--lens-tenant-accent)",
                      }}
                      aria-hidden
                    />
                  )}
                </Link>
              );
            })}
          </nav>
        )}

        <div className="flex-1" />

        <Button
          variant="ghost"
          size="sm"
          onClick={() => setPaletteOpen(true)}
          className="gap-2 text-muted-foreground"
          aria-label="Open command palette"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Jump to…</span>
          <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">
            ⌘K
          </kbd>
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="User menu"
            >
              <Avatar>
                <AvatarFallback>
                  {user ? initials(user.display_name) : "?"}
                </AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col">
                <span className="text-sm">{user?.display_name}</span>
                <span className="text-xs text-muted-foreground">
                  {user?.email}
                </span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => void logout()}>
              <LogOut className="h-4 w-4" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <TenantSwitcher open={paletteOpen} onOpenChange={setPaletteOpen} />
    </header>
  );
}
