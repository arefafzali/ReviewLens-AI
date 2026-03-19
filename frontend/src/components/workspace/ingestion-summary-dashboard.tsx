import React from "react";
import type { ReactNode } from "react";

import type { IngestionAttemptResponse, IngestionKeywordCount, IngestionTimeBucket } from "@/types/api";

type IngestionSummaryDashboardProps = {
  result: IngestionAttemptResponse;
};

function formatAverageRating(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "N/A";
  }
  return `${value.toFixed(2)} / 5`;
}

function safeHistogramCount(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, value) : 0;
}

function renderDateRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start && !end) {
    return "No review dates captured";
  }
  if (start && end) {
    return `${start} to ${end}`;
  }
  return start ?? end ?? "No review dates captured";
}

function Histogram({ histogram }: { histogram: Record<string, number> }): ReactNode {
  const entries = ["5", "4", "3", "2", "1"].map((star) => ({
    label: `${star} star`,
    count: safeHistogramCount(histogram[star]),
  }));
  const maxCount = Math.max(1, ...entries.map((item) => item.count));

  return (
    <ul className="space-y-2" aria-label="Rating distribution histogram">
      {entries.map((item) => {
        const widthPercent = Math.round((item.count / maxCount) * 100);
        return (
          <li key={item.label} className="grid grid-cols-[4.5rem_1fr_2.5rem] items-center gap-2 text-xs">
            <span className="text-muted-foreground">{item.label}</span>
            <div className="h-2 rounded-full bg-muted">
              <div className="h-2 rounded-full bg-primary" style={{ width: `${widthPercent}%` }} />
            </div>
            <span className="text-right font-medium text-foreground">{item.count}</span>
          </li>
        );
      })}
    </ul>
  );
}

function TrendBars({ series }: { series: IngestionTimeBucket[] }): ReactNode {
  if (series.length === 0) {
    return <p className="text-xs text-muted-foreground">Not enough dated reviews to build a trend yet.</p>;
  }

  const maxCount = Math.max(1, ...series.map((item) => Math.max(0, item.count)));
  const recent = series.slice(-8);

  return (
    <div className="space-y-2" aria-label="Review count over time">
      <div className="flex h-20 items-end gap-2 rounded-md bg-muted/40 p-2">
        {recent.map((bucket) => {
          const heightPercent = Math.max(8, Math.round((Math.max(0, bucket.count) / maxCount) * 100));
          return (
            <div key={bucket.date} className="flex min-w-0 flex-1 flex-col items-center justify-end">
              <div className="w-full rounded-sm bg-accent" style={{ height: `${heightPercent}%` }} title={`${bucket.date}: ${bucket.count}`} />
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>{recent[0]?.date ?? ""}</span>
        <span>{recent[recent.length - 1]?.date ?? ""}</span>
      </div>
    </div>
  );
}

function Keywords({ keywords }: { keywords: IngestionKeywordCount[] }): ReactNode {
  if (keywords.length === 0) {
    return <p className="text-xs text-muted-foreground">No recurring keywords were detected yet.</p>;
  }

  return (
    <ul className="flex flex-wrap gap-2" aria-label="Top recurring keywords">
      {keywords.slice(0, 8).map((item) => (
        <li key={item.keyword} className="rounded-full border border-border bg-background px-2.5 py-1 text-xs text-foreground">
          {item.keyword} ({item.count})
        </li>
      ))}
    </ul>
  );
}

export function IngestionSummaryDashboard({ result }: IngestionSummaryDashboardProps): ReactNode {
  const summary = result.summary_snapshot ?? {};
  const totalReviews = typeof summary.total_reviews === "number" ? summary.total_reviews : result.captured_reviews;
  const ratedReviews = typeof summary.rated_reviews === "number" ? summary.rated_reviews : 0;
  const averageRating = typeof summary.average_rating === "number" ? summary.average_rating : null;
  const histogram = typeof summary.rating_histogram === "object" && summary.rating_histogram ? summary.rating_histogram : {};
  const trend = Array.isArray(summary.review_count_over_time) ? summary.review_count_over_time : [];
  const topKeywords = Array.isArray(summary.top_keywords) ? summary.top_keywords : [];
  const dateRange = summary.date_range ?? { start: null, end: null };

  const hasSparseData = totalReviews <= 1;
  const completionHint =
    totalReviews > 0
      ? `${ratedReviews} of ${totalReviews} reviews include ratings.`
      : "No reviews captured yet for this run.";

  return (
    <div className="space-y-4">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border border-border bg-muted/40 p-3">
          <p className="text-xs text-muted-foreground">Captured Reviews</p>
          <p className="mt-1 text-lg font-semibold text-foreground">{totalReviews}</p>
        </div>
        <div className="rounded-md border border-border bg-muted/40 p-3">
          <p className="text-xs text-muted-foreground">Average Rating</p>
          <p className="mt-1 text-lg font-semibold text-foreground">{formatAverageRating(averageRating)}</p>
        </div>
        <div className="rounded-md border border-border bg-muted/40 p-3">
          <p className="text-xs text-muted-foreground">Run Status</p>
          <p className="mt-1 text-lg font-semibold capitalize text-foreground">{result.status}</p>
        </div>
        <div className="rounded-md border border-border bg-muted/40 p-3">
          <p className="text-xs text-muted-foreground">Coverage Window</p>
          <p className="mt-1 text-xs font-medium text-foreground">{renderDateRange(dateRange.start, dateRange.end)}</p>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">{completionHint}</p>

      {hasSparseData ? (
        <div className="rounded-md border border-border bg-background p-3 text-xs text-muted-foreground">
          Sparse dataset detected. Distribution, trend, and keyword signals may be limited until more reviews are ingested.
        </div>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-3">
        <section className="rounded-md border border-border bg-background p-3">
          <h3 className="text-sm font-semibold text-foreground">Rating Distribution</h3>
          <div className="mt-2">
            <Histogram histogram={histogram} />
          </div>
        </section>

        <section className="rounded-md border border-border bg-background p-3">
          <h3 className="text-sm font-semibold text-foreground">Review Trend</h3>
          <div className="mt-2">
            <TrendBars series={trend} />
          </div>
        </section>

        <section className="rounded-md border border-border bg-background p-3">
          <h3 className="text-sm font-semibold text-foreground">Top Keywords</h3>
          <div className="mt-2">
            <Keywords keywords={topKeywords} />
          </div>
        </section>
      </div>
    </div>
  );
}
