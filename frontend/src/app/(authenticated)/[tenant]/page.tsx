"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity as ActivityIcon, Ticket } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SkeletonCard } from "@/components/skeleton-card";
import { SyncStateBadge } from "@/components/sync-state-badge";
import { ActivityFeed } from "@/components/activity-feed";
import { EmptyState } from "@/components/empty-state";
import { api, ApiError } from "@/lib/api";
import { useTenant } from "@/lib/tenant-context";
import type { Activity, JiraIssue, ListResponse } from "@/lib/types";

export default function TenantHomePage() {
  const tenant = useTenant();
  const [tickets, setTickets] = useState<ListResponse<JiraIssue> | null>(null);
  const [activity, setActivity] = useState<ListResponse<Activity> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [t, a] = await Promise.all([
          api.listTickets(tenant.slug, { assignee: "me" }),
          api.listActivity(tenant.slug),
        ]);
        if (!cancelled) {
          setTickets(t);
          setActivity(a);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenant.slug]);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {tenant.name}
          </h1>
          <p className="text-sm text-muted-foreground">
            Everything Netsmart touches for /{tenant.slug}.
          </p>
        </div>
      </header>

      {error && (
        <Card>
          <CardContent className="py-4 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              My open tickets
            </CardTitle>
            <Ticket className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">
              {tickets ? tickets.items.length : "—"}
            </div>
            {tickets && (
              <div className="mt-2">
                <SyncStateBadge sync={tickets.sync} />
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Recent activity
            </CardTitle>
            <ActivityIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">
              {activity ? activity.items.length : "—"}
            </div>
            {activity && (
              <div className="mt-2">
                <SyncStateBadge sync={activity.sync} />
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Quick links</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1 text-sm">
            <Link
              href={`/${tenant.slug}/tickets`}
              className="text-primary hover:underline"
            >
              Jump to tickets →
            </Link>
            <Link
              href={`/${tenant.slug}/activity`}
              className="text-primary hover:underline"
            >
              Full activity feed →
            </Link>
            <Link
              href={`/${tenant.slug}/reports`}
              className="text-primary hover:underline"
            >
              Reports →
            </Link>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Latest activity</CardTitle>
          <CardDescription>
            Consolidated events from every source.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!activity ? (
            <SkeletonCard />
          ) : activity.items.length === 0 ? (
            <EmptyState
              icon={ActivityIcon}
              title={
                activity.sync.state === "never-synced"
                  ? "Never synced"
                  : "No recent activity"
              }
              description={
                activity.sync.state === "never-synced"
                  ? "Enable Jira sync in Settings to start populating the activity feed."
                  : "Activity will appear here as Netsmart does work on this account."
              }
              action={
                activity.sync.state === "never-synced"
                  ? {
                      label: "Enable Jira sync",
                      href: `/${tenant.slug}/settings`,
                    }
                  : undefined
              }
            />
          ) : (
            <ActivityFeed items={activity.items.slice(0, 8)} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
