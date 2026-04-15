import { Circle } from "lucide-react";
import type { Activity } from "@/lib/types";
import { formatRelative } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface Props {
  items: Activity[];
}

export function ActivityFeed({ items }: Props) {
  return (
    <ol className="relative space-y-0">
      {items.map((a, i) => (
        <li key={a.id} className="flex gap-4 pb-5 last:pb-0">
          <div className="flex flex-col items-center">
            <span className="mt-1.5 flex h-6 w-6 items-center justify-center rounded-full border bg-background">
              <Circle className="h-2 w-2 fill-current text-muted-foreground" />
            </span>
            {i !== items.length - 1 && (
              <span className="mt-1 w-px flex-1 bg-border" aria-hidden />
            )}
          </div>
          <div className="flex-1 pb-1">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{a.actor}</span>
              <span className="text-muted-foreground">{a.action}</span>
              <Badge variant="outline" className="font-normal">
                {a.source}
              </Badge>
            </div>
            <p className="mt-0.5 text-sm text-foreground">{a.subject}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {formatRelative(a.occurred_at)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
