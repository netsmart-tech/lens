"use client";

import {
  AlertCircle,
  CheckCircle2,
  CircleDashed,
  Clock,
  Inbox,
  Loader2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { SyncEnvelope, SyncState } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

interface Props {
  sync: SyncEnvelope;
  className?: string;
}

interface Meta {
  label: string;
  variant: React.ComponentProps<typeof Badge>["variant"];
  Icon: typeof CheckCircle2;
  tooltip: (s: SyncEnvelope) => string;
}

const META: Record<SyncState, Meta> = {
  "never-synced": {
    label: "Never synced",
    variant: "outline",
    Icon: CircleDashed,
    tooltip: () => "This source has never been synced. Enable in Settings.",
  },
  "syncing-first-pass": {
    label: "Syncing…",
    variant: "info",
    Icon: Loader2,
    tooltip: (s) =>
      s.progress
        ? `First-pass backfill in progress (${s.progress.pct}%)`
        : "First-pass backfill in progress",
  },
  "synced-but-empty": {
    label: "All caught up",
    variant: "secondary",
    Icon: Inbox,
    tooltip: (s) =>
      s.last_run_at
        ? `No items. Last synced ${formatRelative(s.last_run_at)}.`
        : "No items.",
  },
  stale: {
    label: "Stale",
    variant: "warning",
    Icon: Clock,
    tooltip: (s) =>
      s.last_run_at
        ? `Last synced ${formatRelative(s.last_run_at)}.`
        : "Data may be outdated.",
  },
  fresh: {
    label: "Live",
    variant: "success",
    Icon: CheckCircle2,
    tooltip: (s) =>
      s.last_run_at
        ? `Synced ${formatRelative(s.last_run_at)}.`
        : "Up to date.",
  },
  failed: {
    label: "Sync failed",
    variant: "destructive",
    Icon: AlertCircle,
    tooltip: (s) => s.last_error ?? "Last sync attempt failed.",
  },
};

export function SyncStateBadge({ sync, className }: Props) {
  const meta = META[sync.state];
  const spinning = sync.state === "syncing-first-pass";
  return (
    <Badge
      variant={meta.variant}
      className={className}
      title={meta.tooltip(sync)}
      aria-label={`Sync status: ${meta.label}`}
    >
      <meta.Icon className={spinning ? "h-3 w-3 animate-spin" : "h-3 w-3"} />
      <span>{meta.label}</span>
    </Badge>
  );
}
