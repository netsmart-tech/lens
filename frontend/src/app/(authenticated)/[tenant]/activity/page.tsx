"use client";

import { use, useEffect, useState } from "react";
import { Activity as ActivityIcon } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ActivityFeed } from "@/components/activity-feed";
import { EmptyState } from "@/components/empty-state";
import { SkeletonCard } from "@/components/skeleton-card";
import { SyncStateBadge } from "@/components/sync-state-badge";
import { api, ApiError } from "@/lib/api";
import type { Activity, ListResponse } from "@/lib/types";

interface PageParams {
  params: Promise<{ tenant: string }>;
}

export default function ActivityPage({ params }: PageParams) {
  const { tenant } = use(params);
  const [data, setData] = useState<ListResponse<Activity> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const d = await api.listActivity(tenant);
        if (!cancelled) setData(d);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Failed to load");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenant]);

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Activity</h1>
          <p className="text-sm text-muted-foreground">
            Unified feed of everything Netsmart has done for this tenant.
          </p>
        </div>
        {data && <SyncStateBadge sync={data.sync} />}
      </header>

      {error && (
        <Card>
          <CardContent className="py-4 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Timeline</CardTitle>
          <CardDescription>
            Most recent first. Source-agnostic normalization lives in
            lens_core.activities.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!data ? (
            <SkeletonCard />
          ) : data.items.length === 0 ? (
            <EmptyState
              icon={ActivityIcon}
              title={
                data.sync.state === "never-synced"
                  ? "Never synced"
                  : "No activity yet"
              }
              description={
                data.sync.state === "never-synced"
                  ? "Activity lights up as sync workers populate lens_core.activities."
                  : "Events will appear here as work happens."
              }
              action={
                data.sync.state === "never-synced"
                  ? {
                      label: "Enable sync",
                      href: `/${tenant}/settings`,
                    }
                  : undefined
              }
            />
          ) : (
            <ActivityFeed items={data.items} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
