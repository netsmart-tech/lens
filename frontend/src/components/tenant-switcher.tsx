"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Home, LogOut, Settings } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useTenantOrNull } from "@/lib/tenant-context";

/**
 * ⌘K / Ctrl+K command palette. Lists user's tenants, plus quick-action
 * entries that depend on whether a tenant is currently active.
 *
 * Exports both a standalone dialog (hotkey-triggered) and a hook/ref API
 * so the tenant pill can programmatically open it.
 */
export function TenantSwitcher({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const { tenants, logout } = useAuth();
  const current = useTenantOrNull();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, onOpenChange]);

  const go = (path: string) => {
    onOpenChange(false);
    router.push(path);
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Search tenants, jump to a page…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Tenants">
          {tenants.map((t) => (
            <CommandItem
              key={t.slug}
              value={`tenant ${t.slug} ${t.name}`}
              onSelect={() => go(`/${t.slug}`)}
            >
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: t.color_hex }}
                aria-hidden
              />
              <span className="flex-1">{t.name}</span>
              {current?.slug === t.slug && (
                <span className="text-xs text-muted-foreground">current</span>
              )}
            </CommandItem>
          ))}
        </CommandGroup>

        {current && (
          <>
            <CommandSeparator />
            <CommandGroup heading={`${current.name} — Quick actions`}>
              <CommandItem
                value="home"
                onSelect={() => go(`/${current.slug}`)}
              >
                <Home />
                <span>Home</span>
              </CommandItem>
              <CommandItem
                value="tickets"
                onSelect={() => go(`/${current.slug}/tickets`)}
              >
                <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[10px] font-semibold">
                  T
                </span>
                <span>My tickets</span>
              </CommandItem>
              <CommandItem
                value="activity"
                onSelect={() => go(`/${current.slug}/activity`)}
              >
                <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[10px] font-semibold">
                  A
                </span>
                <span>Activity</span>
              </CommandItem>
              <CommandItem
                value="settings"
                onSelect={() => go(`/${current.slug}/settings`)}
              >
                <Settings />
                <span>Settings</span>
              </CommandItem>
            </CommandGroup>
          </>
        )}

        <CommandSeparator />
        <CommandGroup heading="Account">
          <CommandItem
            value="logout"
            onSelect={() => {
              onOpenChange(false);
              void logout();
            }}
          >
            <LogOut />
            <span>Sign out</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
