"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { JiraIssueDetail } from "@/lib/types";
import { formatDateTime, formatRelative } from "@/lib/utils";

interface Params {
  params: Promise<{ tenant: string; key: string }>;
}

export default function TicketDetailPage({ params }: Params) {
  const { tenant, key } = use(params);
  const decodedKey = decodeURIComponent(key);
  const [issue, setIssue] = useState<JiraIssueDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const i = await api.getTicket(tenant, decodedKey);
        if (!cancelled) setIssue(i);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Failed to load");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenant, decodedKey]);

  return (
    <div className="space-y-4">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-3 gap-1">
          <Link href={`/${tenant}/tickets`}>
            <ArrowLeft className="h-3.5 w-3.5" />
            Tickets
          </Link>
        </Button>
      </div>

      {error && (
        <Card>
          <CardContent className="py-4 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      )}

      {!issue && !error ? (
        <Card>
          <CardHeader className="space-y-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-6 w-2/3" />
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
          </CardContent>
        </Card>
      ) : issue ? (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <code className="font-mono">{issue.key}</code>
                <span>•</span>
                <Badge variant="secondary">{issue.status}</Badge>
                {issue.priority && (
                  <Badge variant="outline">{issue.priority}</Badge>
                )}
              </div>
              <CardTitle className="mt-2 text-xl">{issue.summary}</CardTitle>
              <CardDescription>
                Assignee: {issue.assignee ?? "Unassigned"} · Reporter:{" "}
                {issue.reporter ?? "—"} · Updated{" "}
                {formatRelative(issue.updated)}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {issue.description ? (
                <div className="whitespace-pre-wrap text-sm leading-relaxed">
                  {issue.description}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No description.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Comments ({issue.comments.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {issue.comments.length === 0 ? (
                <p className="text-sm text-muted-foreground">No comments.</p>
              ) : (
                issue.comments.map((c, i) => (
                  <div key={c.id}>
                    {i > 0 && <Separator className="mb-4" />}
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">
                        {c.author}
                      </span>
                      <span title={formatDateTime(c.created)}>
                        {formatRelative(c.created)}
                      </span>
                    </div>
                    <div className="mt-1 whitespace-pre-wrap text-sm">
                      {c.body}
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
