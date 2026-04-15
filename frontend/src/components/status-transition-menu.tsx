"use client";

import { useCallback, useState } from "react";
import { ChevronDown, Loader2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { api, ApiError } from "@/lib/api";
import type { JiraIssueDetail, Transition } from "@/lib/types";

interface StatusTransitionMenuProps {
  tenant: string;
  issueKey: string;
  status: string | null;
  onTransitioned: (updated: JiraIssueDetail) => void;
  onError?: (message: string) => void;
}

export function StatusTransitionMenu({
  tenant,
  issueKey,
  status,
  onTransitioned,
  onError,
}: StatusTransitionMenuProps) {
  const [open, setOpen] = useState(false);
  const [transitions, setTransitions] = useState<Transition[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);

  const loadTransitions = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await api.listTransitions(tenant, issueKey);
      setTransitions(res.transitions);
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.message : "Failed to load transitions",
      );
      setTransitions(null);
    } finally {
      setLoading(false);
    }
  }, [tenant, issueKey]);

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (next) {
      // Always re-fetch on open — transitions depend on current workflow state
      // which can shift after each transition.
      void loadTransitions();
    }
  };

  const handleSelect = async (t: Transition) => {
    setOpen(false);
    setApplying(true);
    setInlineError(null);
    try {
      const updated = await api.applyTransition(tenant, issueKey, t.id);
      onTransitioned(updated);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to apply transition";
      setInlineError(message);
      onError?.(message);
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <DropdownMenu open={open} onOpenChange={handleOpenChange}>
        <DropdownMenuTrigger asChild disabled={applying}>
          <button
            type="button"
            aria-label={`Change status (current: ${status ?? "unknown"})`}
            aria-haspopup="menu"
            aria-expanded={open}
            className="inline-flex"
          >
            <Badge
              variant="secondary"
              className={cn(
                "cursor-pointer gap-1 pr-1.5 transition-colors hover:bg-muted",
                applying && "opacity-80",
              )}
            >
              {applying && <Loader2 className="h-3 w-3 animate-spin" />}
              <span>{status ?? "—"}</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </Badge>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-[12rem]">
          {loading ? (
            <div className="space-y-1 p-1">
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-5/6" />
              <Skeleton className="h-6 w-4/6" />
            </div>
          ) : loadError ? (
            <div className="px-2 py-1.5 text-sm text-destructive">
              {loadError}
            </div>
          ) : !transitions || transitions.length === 0 ? (
            <div className="px-2 py-1.5 text-sm text-muted-foreground">
              No transitions available
            </div>
          ) : (
            transitions.map((t) => {
              const sameName =
                t.name.trim().toLowerCase() ===
                t.to_status.trim().toLowerCase();
              return (
                <DropdownMenuItem
                  key={t.id}
                  onSelect={(e) => {
                    e.preventDefault();
                    void handleSelect(t);
                  }}
                  className="flex items-center justify-between gap-3"
                >
                  <span className="text-sm">
                    {sameName ? `→ ${t.to_status}` : `${t.name} → ${t.to_status}`}
                  </span>
                </DropdownMenuItem>
              );
            })
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      {inlineError && (
        <p className="text-xs text-destructive" role="alert">
          {inlineError}
        </p>
      )}
    </div>
  );
}
