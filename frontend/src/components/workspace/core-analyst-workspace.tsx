"use client";

import React from "react";
import { useState } from "react";
import type { ReactNode } from "react";

import { IngestionPanel } from "@/components/workspace/ingestion-panel";
import { IngestionSummaryDashboard } from "@/components/workspace/ingestion-summary-dashboard";
import type { IngestionAttemptResponse } from "@/types/api";

type SectionStatus = "loading" | "ready";

type WorkspaceSection = {
  id: string;
  title: string;
  description: string;
  status: SectionStatus;
  placeholder: ReactNode;
};

const SECTIONS: WorkspaceSection[] = [
  {
    id: "ingestion-summary",
    title: "Ingestion Summary",
    description: "Show outcome, capture counts, analytics highlights, and extraction diagnostics.",
    status: "loading",
    placeholder: (
      <div className="grid gap-2 sm:grid-cols-3">
        <div className="h-14 animate-pulse rounded-md bg-muted" />
        <div className="h-14 animate-pulse rounded-md bg-muted" />
        <div className="h-14 animate-pulse rounded-md bg-muted" />
      </div>
    ),
  },
  {
    id: "suggested-questions",
    title: "Suggested Questions",
    description: "Display grounded starter prompts generated from ingested reviews.",
    status: "loading",
    placeholder: (
      <ul className="space-y-2">
        <li className="h-8 animate-pulse rounded-md bg-muted" />
        <li className="h-8 animate-pulse rounded-md bg-muted" />
        <li className="h-8 animate-pulse rounded-md bg-muted" />
      </ul>
    ),
  },
  {
    id: "analyst-chat",
    title: "Analyst Chat",
    description: "Host scoped multi-turn Q&A with source-grounded answers from ingested reviews.",
    status: "loading",
    placeholder: (
      <div className="space-y-3">
        <div className="h-24 animate-pulse rounded-md bg-muted" />
        <div className="h-24 animate-pulse rounded-md bg-muted" />
        <div className="h-10 animate-pulse rounded-md bg-muted" />
      </div>
    ),
  },
];

function SectionStatusBadge({ status }: { status: SectionStatus }): ReactNode {
  if (status === "ready") {
    return (
      <span className="inline-flex rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
        Ready
      </span>
    );
  }

  return (
    <span className="inline-flex rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
      Loading
    </span>
  );
}

function WorkspaceSectionCard({ section }: { section: WorkspaceSection }): ReactNode {
  return (
    <section aria-labelledby={section.id} className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 id={section.id} className="text-base font-semibold tracking-tight">
            {section.title}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">{section.description}</p>
        </div>
        <SectionStatusBadge status={section.status} />
      </div>
      {section.placeholder}
    </section>
  );
}

export function CoreAnalystWorkspace(): ReactNode {
  const [latestIngestion, setLatestIngestion] = useState<IngestionAttemptResponse | null>(null);

  const summarySection: WorkspaceSection = {
    id: "ingestion-summary",
    title: "Ingestion Summary",
    description: "Show outcome, capture counts, analytics highlights, and extraction diagnostics.",
    status: latestIngestion ? "ready" : "loading",
    placeholder: latestIngestion ? <IngestionSummaryDashboard result={latestIngestion} /> : (
      <div className="grid gap-2 sm:grid-cols-3">
        <div className="h-14 animate-pulse rounded-md bg-muted" />
        <div className="h-14 animate-pulse rounded-md bg-muted" />
        <div className="h-14 animate-pulse rounded-md bg-muted" />
      </div>
    ),
  };

  const trailingSections = SECTIONS.filter((section) => section.id !== "ingestion-summary");

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <WorkspaceSectionCard
        section={{
          id: "ingestion-panel",
          title: "Ingestion Panel",
          description: "Submit a URL or upload CSV reviews to start a run.",
          status: "ready",
          placeholder: <IngestionPanel onIngestionSuccess={setLatestIngestion} />,
        }}
      />
      <WorkspaceSectionCard key={summarySection.id} section={summarySection} />
      {trailingSections.map((section) => (
        <WorkspaceSectionCard key={section.id} section={section} />
      ))}
    </div>
  );
}
