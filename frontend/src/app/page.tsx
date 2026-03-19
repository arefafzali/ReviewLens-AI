import React from "react";
import { AppShell } from "@/components/layout/app-shell";
import { CoreAnalystWorkspace } from "@/components/workspace/core-analyst-workspace";

export default function HomePage() {
  return (
    <AppShell
      title="Analyst Workspace"
      subtitle="Minimal core loop surface for ingestion, summary confidence checks, grounded starter questions, and scoped chat."
    >
      <CoreAnalystWorkspace />
    </AppShell>
  );
}
