"use client";

import { ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Tenant } from "@/lib/types";

interface Props {
  tenant: Tenant;
  onClick?: () => void;
  className?: string;
}

/**
 * Visible anchor for the cmdk tenant switcher. Clicking opens the palette;
 * ⌘K / Ctrl+K does the same. Color swatch uses the tenant accent color
 * directly (no CSS-var indirection here — this component is the palette
 * *invocation*, not tenant-scoped chrome).
 */
export function TenantPill({ tenant, onClick, className }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Switch tenant (current: ${tenant.name})`}
      className={cn(
        "inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      <span
        className="h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: tenant.color_hex }}
        aria-hidden
      />
      <span className="truncate max-w-[14ch]">{tenant.name}</span>
      <ChevronsUpDown className="h-3.5 w-3.5 text-muted-foreground" />
    </button>
  );
}
