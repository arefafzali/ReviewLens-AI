import React from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <AppShell
      title="Analyst Workspace Scaffold"
      subtitle="Frontend foundations are in place for URL/CSV ingestion, summary, and guardrailed multi-turn review Q&A."
    >
      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">App Status</h2>
          <p className="mt-2 text-sm text-foreground">
            Next.js App Router, TypeScript, Tailwind, and shadcn-compatible configuration are initialized.
          </p>
        </article>
        <article className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Next Milestone</h2>
          <p className="mt-2 text-sm text-foreground">
            Build core analyst workspace flow: ingestion, capture summary, and scoped Q&A against ingested review context.
          </p>
        </article>
      </section>
      <div className="mt-6">
        <Button variant="secondary" type="button" disabled>
          Workspace Setup In Progress
        </Button>
      </div>
    </AppShell>
  );
}
