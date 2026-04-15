"use client";

import { use, useEffect, useState } from "react";
import { Ticket } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { SkeletonTable } from "@/components/skeleton-table";
import { SyncStateBadge } from "@/components/sync-state-badge";
import { TicketsTable } from "@/components/tickets-table";
import { api, ApiError } from "@/lib/api";
import type { JiraIssue, ListResponse } from "@/lib/types";

interface PageParams {
  params: Promise<{ tenant: string }>;
}

type Filter = "me" | "all";

export default function TicketsPage({ params }: PageParams) {
  const { tenant } = use(params);
  const [data, setData] = useState<ListResponse<JiraIssue> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("me");

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    (async () => {
      try {
        const d = await api.listTickets(tenant, { assignee: filter });
        if (!cancelled) setData(d);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Failed to load");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenant, filter]);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tickets</h1>
          <p className="text-sm text-muted-foreground">
            Jira issues synced from this tenant&apos;s sites.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-md border bg-background p-0.5">
            <Button
              size="sm"
              variant={filter === "me" ? "secondary" : "ghost"}
              onClick={() => setFilter("me")}
              className="h-8"
            >
              Assigned to me
            </Button>
            <Button
              size="sm"
              variant={filter === "all" ? "secondary" : "ghost"}
              onClick={() => setFilter("all")}
              className="h-8"
            >
              All
            </Button>
          </div>
          {data && <SyncStateBadge sync={data.sync} />}
        </div>
      </header>

      {error && (
        <Card>
          <CardContent className="py-4 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      )}

      {!data ? (
        <SkeletonTable />
      ) : data.items.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="sr-only">No tickets</CardTitle>
            <CardDescription className="sr-only">
              Empty state details
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.sync.state === "never-synced" ? (
              <EmptyState
                icon={Ticket}
                title="Never synced"
                description="Enable Jira sync in Settings to pull this tenant's tickets into Lens."
                action={{
                  label: "Go to Settings",
                  href: `/${tenant}/settings`,
                }}
              />
            ) : data.sync.state === "syncing-first-pass" ? (
              <EmptyState
                icon={Ticket}
                title="Syncing for the first time"
                description={
                  data.sync.progress
                    ? `Loading historical tickets (${data.sync.progress.pct}%). This page will populate as results arrive.`
                    : "Loading historical tickets. This page will populate as results arrive."
                }
              />
            ) : data.sync.state === "failed" ? (
              <EmptyState
                icon={Ticket}
                title="Sync failed"
                description={
                  data.sync.last_error ??
                  "The last sync attempt failed. Check Settings for details."
                }
                action={{
                  label: "View sync state",
                  href: `/${tenant}/settings`,
                }}
              />
            ) : (
              <EmptyState
                icon={Ticket}
                title={
                  filter === "me"
                    ? "You have no open tickets"
                    : "No tickets"
                }
                description={
                  filter === "me"
                    ? "Switch to 'All' to see everything in this tenant."
                    : "No tickets have been synced yet."
                }
              />
            )}
          </CardContent>
        </Card>
      ) : (
        <TicketsTable tenantSlug={tenant} issues={data.items} />
      )}
    </div>
  );
}
