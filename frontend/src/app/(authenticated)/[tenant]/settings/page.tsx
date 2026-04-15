"use client";

import { Settings as SettingsIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Per-tenant sources, sync cadence, and access controls.
        </p>
      </header>

      <Card aria-disabled className="opacity-80">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10">
                <SettingsIcon className="h-4 w-4 text-primary" />
              </div>
              <div>
                <CardTitle className="text-base">
                  Sources &amp; sync cadence
                </CardTitle>
                <CardDescription>
                  Turn Jira / FortiGate / ServiceNow on per tenant.
                </CardDescription>
              </div>
            </div>
            <Badge variant="outline">Coming in Phase 2</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Phase 1 seeds sources via the <code>lens add-tenant</code> CLI.
            This page will let you toggle sources and tune sync cadence once
            Phase 2 ships.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
