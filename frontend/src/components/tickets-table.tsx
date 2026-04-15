"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { JiraIssue } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

interface Props {
  tenantSlug: string;
  issues: JiraIssue[];
}

function priorityVariant(
  p: string | null,
): React.ComponentProps<typeof Badge>["variant"] {
  if (!p) return "outline";
  const v = p.toLowerCase();
  if (v.includes("highest") || v.includes("blocker")) return "destructive";
  if (v.includes("high")) return "warning";
  if (v.includes("medium")) return "info";
  if (v.includes("low")) return "secondary";
  return "outline";
}

function statusVariant(
  status: string,
): React.ComponentProps<typeof Badge>["variant"] {
  const s = status.toLowerCase();
  if (s.includes("done") || s.includes("closed") || s.includes("resolved"))
    return "success";
  if (s.includes("progress") || s.includes("review")) return "info";
  if (s.includes("block")) return "destructive";
  return "secondary";
}

export function TicketsTable({ tenantSlug, issues }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/30 hover:bg-muted/30">
            <TableHead className="w-[120px]">Key</TableHead>
            <TableHead>Summary</TableHead>
            <TableHead className="w-[130px]">Status</TableHead>
            <TableHead className="w-[110px]">Priority</TableHead>
            <TableHead className="w-[140px]">Updated</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {issues.map((issue) => (
            <TableRow key={issue.key} className="cursor-pointer">
              <TableCell className="font-mono text-xs">
                <Link
                  href={`/${tenantSlug}/tickets/${encodeURIComponent(issue.key)}`}
                  className="hover:underline"
                >
                  {issue.key}
                </Link>
              </TableCell>
              <TableCell className="max-w-0">
                <Link
                  href={`/${tenantSlug}/tickets/${encodeURIComponent(issue.key)}`}
                  className="block truncate hover:underline"
                  title={issue.summary}
                >
                  {issue.summary}
                </Link>
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant(issue.status)}>
                  {issue.status}
                </Badge>
              </TableCell>
              <TableCell>
                {issue.priority ? (
                  <Badge variant={priorityVariant(issue.priority)}>
                    {issue.priority}
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {formatRelative(issue.updated)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
