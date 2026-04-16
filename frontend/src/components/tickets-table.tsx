"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Check, ChevronDown, ChevronUp, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { JiraIssue } from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";

interface Props {
  tenantSlug: string;
  issues: JiraIssue[];
}

type SortKey = "key" | "summary" | "status" | "priority" | "updated";
type SortDir = "asc" | "desc";
interface SortState {
  key: SortKey;
  dir: SortDir;
}

interface FilterState {
  key: string;
  summary: string;
  status: string[];
  priority: string[];
}

const DEFAULT_SORT: SortState = { key: "updated", dir: "desc" };
const EMPTY_FILTERS: FilterState = {
  key: "",
  summary: "",
  status: [],
  priority: [],
};

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
  status: string | null,
): React.ComponentProps<typeof Badge>["variant"] {
  if (!status) return "outline";
  const s = status.toLowerCase();
  if (s.includes("done") || s.includes("closed") || s.includes("resolved"))
    return "success";
  if (s.includes("progress") || s.includes("review")) return "info";
  if (s.includes("block")) return "destructive";
  return "secondary";
}

function cmp(a: string | null, b: string | null): number {
  if (a === b) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
}

function cmpDate(a: string | null, b: string | null): number {
  const ta = a ? new Date(a).getTime() : NaN;
  const tb = b ? new Date(b).getTime() : NaN;
  if (isNaN(ta) && isNaN(tb)) return 0;
  if (isNaN(ta)) return 1;
  if (isNaN(tb)) return -1;
  return ta - tb;
}

interface MultiSelectFilterProps {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
  onClear: () => void;
}

function MultiSelectFilter({
  label,
  options,
  selected,
  onToggle,
  onClear,
}: MultiSelectFilterProps) {
  const summary =
    selected.length === 0
      ? "All"
      : selected.length === 1
        ? selected[0]
        : `${selected.length} selected`;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex h-7 w-full items-center justify-between gap-1 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          selected.length === 0 && "text-muted-foreground",
        )}
        aria-label={`Filter by ${label}`}
      >
        <span className="truncate">{summary}</span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-60" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-[12rem]">
        {options.length === 0 ? (
          <div className="px-2 py-1.5 text-xs text-muted-foreground">
            No options
          </div>
        ) : (
          <>
            {options.map((opt) => {
              const isSelected = selected.includes(opt);
              return (
                <DropdownMenuItem
                  key={opt}
                  onSelect={(e) => {
                    e.preventDefault();
                    onToggle(opt);
                  }}
                  className="text-xs"
                >
                  <span className="flex h-3.5 w-3.5 items-center justify-center">
                    {isSelected && <Check className="h-3.5 w-3.5" />}
                  </span>
                  <span className="truncate">{opt}</span>
                </DropdownMenuItem>
              );
            })}
            {selected.length > 0 && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onSelect={(e) => {
                    e.preventDefault();
                    onClear();
                  }}
                  className="text-xs text-muted-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                  Clear
                </DropdownMenuItem>
              </>
            )}
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SortIcon({ dir }: { dir: SortDir | null }) {
  if (dir === "asc") return <ChevronUp className="h-3.5 w-3.5" />;
  if (dir === "desc") return <ChevronDown className="h-3.5 w-3.5" />;
  return null;
}

interface SortableHeaderProps {
  label: string;
  column: SortKey;
  sort: SortState | null;
  onToggle: (k: SortKey) => void;
  className?: string;
}

function SortableHeader({
  label,
  column,
  sort,
  onToggle,
  className,
}: SortableHeaderProps) {
  const active = sort?.key === column;
  return (
    <TableHead className={className}>
      <button
        type="button"
        onClick={() => onToggle(column)}
        className={cn(
          "-ml-1 inline-flex items-center gap-1 rounded px-1 py-0.5 text-left text-xs font-medium uppercase tracking-wide transition-colors hover:bg-muted/60",
          active && "text-foreground",
        )}
      >
        {label}
        <SortIcon dir={active ? sort!.dir : null} />
      </button>
    </TableHead>
  );
}

export function TicketsTable({ tenantSlug, issues }: Props) {
  const [sort, setSort] = useState<SortState | null>(DEFAULT_SORT);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);

  // Distinct status/priority values from the current dataset power the
  // dropdown options — keeps filtering exact-match and avoids typos.
  const statusOptions = useMemo(
    () =>
      Array.from(
        new Set(issues.map((i) => i.status).filter((s): s is string => !!s)),
      ).sort(),
    [issues],
  );
  const priorityOptions = useMemo(
    () =>
      Array.from(
        new Set(issues.map((i) => i.priority).filter((p): p is string => !!p)),
      ).sort(),
    [issues],
  );

  const toggleSort = (k: SortKey) => {
    setSort((prev) => {
      if (!prev || prev.key !== k) return { key: k, dir: "asc" };
      if (prev.dir === "asc") return { key: k, dir: "desc" };
      return null; // unsorted
    });
  };

  const filtered = useMemo(() => {
    const kq = filters.key.trim().toLowerCase();
    const sq = filters.summary.trim().toLowerCase();
    return issues.filter((i) => {
      if (kq && !i.key.toLowerCase().includes(kq)) return false;
      if (sq && !i.summary.toLowerCase().includes(sq)) return false;
      if (
        filters.status.length > 0 &&
        (!i.status || !filters.status.includes(i.status))
      )
        return false;
      if (
        filters.priority.length > 0 &&
        (!i.priority || !filters.priority.includes(i.priority))
      )
        return false;
      return true;
    });
  }, [issues, filters]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    const { key, dir } = sort;
    const mult = dir === "asc" ? 1 : -1;
    const out = [...filtered];
    out.sort((a, b) => {
      if (key === "updated") return cmpDate(a.updated, b.updated) * mult;
      return cmp(a[key] as string | null, b[key] as string | null) * mult;
    });
    return out;
  }, [filtered, sort]);

  const hasActiveFilter =
    !!filters.key ||
    !!filters.summary ||
    filters.status.length > 0 ||
    filters.priority.length > 0;

  const toggleValue = (field: "status" | "priority", value: string) => {
    setFilters((f) => {
      const current = f[field];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      return { ...f, [field]: next };
    });
  };

  return (
    <div className="overflow-hidden rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/30 hover:bg-muted/30">
            <SortableHeader
              label="Key"
              column="key"
              sort={sort}
              onToggle={toggleSort}
              className="w-[120px]"
            />
            <SortableHeader
              label="Summary"
              column="summary"
              sort={sort}
              onToggle={toggleSort}
            />
            <SortableHeader
              label="Status"
              column="status"
              sort={sort}
              onToggle={toggleSort}
              className="w-[150px]"
            />
            <SortableHeader
              label="Priority"
              column="priority"
              sort={sort}
              onToggle={toggleSort}
              className="w-[130px]"
            />
            <SortableHeader
              label="Updated"
              column="updated"
              sort={sort}
              onToggle={toggleSort}
              className="w-[140px]"
            />
          </TableRow>
          <TableRow className="bg-muted/10 hover:bg-muted/10">
            <TableHead className="py-1.5">
              <Input
                value={filters.key}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, key: e.target.value }))
                }
                placeholder="Filter…"
                className="h-7 text-xs"
              />
            </TableHead>
            <TableHead className="py-1.5">
              <Input
                value={filters.summary}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, summary: e.target.value }))
                }
                placeholder="Filter summary…"
                className="h-7 text-xs"
              />
            </TableHead>
            <TableHead className="py-1.5">
              <MultiSelectFilter
                label="Status"
                options={statusOptions}
                selected={filters.status}
                onToggle={(v) => toggleValue("status", v)}
                onClear={() => setFilters((f) => ({ ...f, status: [] }))}
              />
            </TableHead>
            <TableHead className="py-1.5">
              <MultiSelectFilter
                label="Priority"
                options={priorityOptions}
                selected={filters.priority}
                onToggle={(v) => toggleValue("priority", v)}
                onClear={() => setFilters((f) => ({ ...f, priority: [] }))}
              />
            </TableHead>
            <TableHead className="py-1.5">
              {hasActiveFilter && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-full gap-1 text-xs"
                  onClick={() => setFilters(EMPTY_FILTERS)}
                >
                  <X className="h-3 w-3" />
                  Clear
                </Button>
              )}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={5}
                className="py-6 text-center text-xs text-muted-foreground"
              >
                No tickets match the current filters.
              </TableCell>
            </TableRow>
          ) : (
            sorted.map((issue) => (
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
                  {issue.status ? (
                    <Badge variant={statusVariant(issue.status)}>
                      {issue.status}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
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
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
