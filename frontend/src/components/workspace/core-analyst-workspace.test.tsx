import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import { apiClient } from "@/lib/api";

import { CoreAnalystWorkspace } from "./core-analyst-workspace";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiClient: {
      postEnsureContext: vi.fn(),
      postUrlIngestion: vi.fn(),
      postCsvIngestion: vi.fn(),
    },
  };
});

describe("CoreAnalystWorkspace", () => {
  it("updates ingestion summary section after successful URL ingestion", async () => {
    vi.mocked(apiClient.postEnsureContext).mockResolvedValue({
      workspace_id: "workspace-1",
      product_id: "product-1",
      created_workspace: false,
      created_product: false,
    });
    vi.mocked(apiClient.postUrlIngestion).mockResolvedValueOnce({
      ingestion_run_id: "run-456",
      source_type: "scrape",
      status: "success",
      outcome_code: "ok",
      captured_reviews: 12,
      message: "Ingestion completed successfully.",
      warnings: [],
      diagnostics: { parser: "gpt_markdown_chunks" },
      summary_snapshot: {
        total_reviews: 12,
        rated_reviews: 10,
        average_rating: 4.25,
        rating_histogram: { "1": 1, "2": 1, "3": 2, "4": 4, "5": 4 },
        review_count_over_time: [
          { date: "2026-03-10", count: 3 },
          { date: "2026-03-11", count: 4 },
          { date: "2026-03-12", count: 5 },
        ],
        date_range: { start: "2026-03-10", end: "2026-03-12" },
        top_keywords: [
          { keyword: "support", count: 5 },
          { keyword: "onboarding", count: 3 },
        ],
        suggested_questions: [
          "What themes appear most often?",
          "What are the top strengths users mention?",
          "Which concerns appear in lower-rated reviews?",
        ],
      },
      started_at: "2026-03-19T10:00:00Z",
      completed_at: "2026-03-19T10:01:00Z",
    });

    render(<CoreAnalystWorkspace />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://www.g2.com/products/example/reviews" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));

    expect(await screen.findByText("run-456")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Ingestion Summary" })).toBeInTheDocument();
    expect(await screen.findByText("4.25 / 5")).toBeInTheDocument();
    expect(await screen.findByText("support (5)")).toBeInTheDocument();
    expect(await screen.findByText("2026-03-10 to 2026-03-12")).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: "What themes appear most often?" }));

    expect(await screen.findByText("Question queued for grounded chat analysis.")).toBeInTheDocument();
    expect(await screen.findByText(/Conversation started\. Showing top suggestion\./i)).toBeInTheDocument();
  });
});
