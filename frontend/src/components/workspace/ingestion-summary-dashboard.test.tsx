import React from "react";
import { render, screen } from "@testing-library/react";

import type { IngestionAttemptResponse } from "@/types/api";

import { IngestionSummaryDashboard } from "./ingestion-summary-dashboard";

function buildResult(overrides: Partial<IngestionAttemptResponse> = {}): IngestionAttemptResponse {
  return {
    ingestion_run_id: "run-1",
    source_type: "scrape",
    status: "success",
    outcome_code: "ok",
    captured_reviews: 6,
    message: "Ingestion completed successfully.",
    warnings: [],
    diagnostics: {},
    summary_snapshot: {
      total_reviews: 6,
      rated_reviews: 5,
      average_rating: 4.1,
      rating_histogram: { "1": 0, "2": 1, "3": 1, "4": 2, "5": 2 },
      review_count_over_time: [
        { date: "2026-03-01", count: 2 },
        { date: "2026-03-02", count: 1 },
        { date: "2026-03-03", count: 3 },
      ],
      date_range: { start: "2026-03-01", end: "2026-03-03" },
      top_keywords: [
        { keyword: "support", count: 3 },
        { keyword: "reporting", count: 2 },
      ],
    },
    started_at: "2026-03-19T10:00:00Z",
    completed_at: "2026-03-19T10:01:00Z",
    ...overrides,
  };
}

describe("IngestionSummaryDashboard", () => {
  it("renders realistic analytics including histogram, trend, and keywords", () => {
    render(<IngestionSummaryDashboard result={buildResult()} />);

    expect(screen.getByText("Captured Reviews")).toBeInTheDocument();
    expect(screen.getByText("4.10 / 5")).toBeInTheDocument();
    expect(screen.getByLabelText("Rating distribution histogram")).toBeInTheDocument();
    expect(screen.getByLabelText("Review count over time")).toBeInTheDocument();
    expect(screen.getByText("support (3)")).toBeInTheDocument();
    expect(screen.getByText("reporting (2)")).toBeInTheDocument();
  });

  it("handles sparse analytics safely", () => {
    render(
      <IngestionSummaryDashboard
        result={buildResult({
          captured_reviews: 1,
          summary_snapshot: {
            total_reviews: 1,
            rated_reviews: 0,
            average_rating: null,
            rating_histogram: { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 },
            review_count_over_time: [],
            date_range: { start: null, end: null },
            top_keywords: [],
          },
        })}
      />,
    );

    expect(screen.getByText(/sparse dataset detected/i)).toBeInTheDocument();
    expect(screen.getByText(/not enough dated reviews/i)).toBeInTheDocument();
    expect(screen.getByText(/no recurring keywords/i)).toBeInTheDocument();
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("gracefully handles malformed summary payload shapes", () => {
    render(
      <IngestionSummaryDashboard
        result={buildResult({
          captured_reviews: 0,
          summary_snapshot: {
            total_reviews: 0,
            rated_reviews: 0,
            average_rating: null,
            rating_histogram: { "1": Number.NaN, "5": -3 },
            review_count_over_time: [{ date: "2026-03-03", count: 2 }, { date: "", count: 5 }] as never,
            top_keywords: [{ keyword: "", count: 2 }, { keyword: "support", count: -10 }] as never,
            date_range: { start: 123 as never, end: null },
          },
        })}
      />,
    );

    expect(screen.getByText(/no review dates captured/i)).toBeInTheDocument();
    expect(screen.getByText("support (0)")).toBeInTheDocument();
    expect(screen.getByText("No reviews captured yet for this run.")).toBeInTheDocument();
  });
});
