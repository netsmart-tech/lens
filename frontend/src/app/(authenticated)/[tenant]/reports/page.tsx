"use client";

import { FileText, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function ReportsPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
        <p className="text-sm text-muted-foreground">
          Auto-generated client-facing work summaries, narrated from activity
          data.
        </p>
      </header>

      <Card aria-disabled className="opacity-80">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10">
                <Sparkles className="h-4 w-4 text-primary" />
              </div>
              <div>
                <CardTitle className="text-base">Report builder</CardTitle>
                <CardDescription>
                  Select a template + date range and generate a PDF.
                </CardDescription>
              </div>
            </div>
            <Badge variant="outline">Coming in Phase 3</Badge>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-dashed p-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <FileText className="h-4 w-4 text-muted-foreground" />
              Weekly ops brief
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Tickets closed, incidents, policy changes — week-over-week.
            </p>
          </div>
          <div className="rounded-md border border-dashed p-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <FileText className="h-4 w-4 text-muted-foreground" />
              Monthly value summary
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Client-facing summary of every engagement touch-point this month.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
