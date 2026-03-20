import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ApiClientError, apiClient } from "@/lib/api";

import { IngestionPanel } from "./ingestion-panel";

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

describe("IngestionPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.postEnsureContext).mockResolvedValue({
      workspace_id: "workspace-1",
      product_id: "product-1",
      created_workspace: false,
      created_product: false,
    });
  });

  it("shows validation error for invalid URL submission", async () => {
    render(<IngestionPanel />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "not-a-url" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));

    expect(await screen.findByText(/enter a valid url/i)).toBeInTheDocument();
    expect(apiClient.postUrlIngestion).not.toHaveBeenCalled();
  });

  it("shows CSV fallback guidance when URL ingestion is blocked", async () => {
    vi.mocked(apiClient.postUrlIngestion).mockResolvedValueOnce({
      ingestion_run_id: "run-blocked",
      source_type: "scrape",
      status: "failed",
      outcome_code: "blocked",
      captured_reviews: 0,
      message: "Source blocked extraction attempts.",
      warnings: [],
      diagnostics: {},
      summary_snapshot: {},
      started_at: "2026-03-19T10:00:00Z",
      completed_at: "2026-03-19T10:00:05Z",
    });

    render(<IngestionPanel />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://www.g2.com/products/example/reviews" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));

    expect(await screen.findByText(/url ingestion may be incomplete/i)).toBeInTheDocument();
    expect(apiClient.postEnsureContext).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Switch to CSV fallback" }));
    expect(screen.getByRole("button", { name: "Run CSV Ingestion" })).toBeInTheDocument();
  });

  it("submits CSV ingestion and updates workspace callback on success", async () => {
    const onIngestionSuccess = vi.fn();
    vi.mocked(apiClient.postCsvIngestion).mockResolvedValueOnce({
      ingestion_run_id: "run-csv-123",
      source_type: "csv_upload",
      status: "success",
      outcome_code: "ok",
      captured_reviews: 2,
      message: "CSV ingestion completed successfully.",
      warnings: [],
      diagnostics: { parser: "csv_alias_mapping" },
      summary_snapshot: {
        total_reviews: 2,
        rated_reviews: 2,
        average_rating: 4.5,
      },
      started_at: "2026-03-19T11:00:00Z",
      completed_at: "2026-03-19T11:00:01Z",
    });

    render(<IngestionPanel onIngestionSuccess={onIngestionSuccess} />);

    fireEvent.click(screen.getByRole("tab", { name: "Upload CSV" }));
    const csvFile = new File(["body,rating\nGreat,5\n"], "reviews.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText(/review csv file/i), {
      target: { files: [csvFile] },
    });

    fireEvent.click(screen.getByRole("button", { name: "Run CSV Ingestion" }));

    expect(await screen.findByText(/csv ingestion completed successfully/i)).toBeInTheDocument();
    expect(await screen.findByText("run-csv-123")).toBeInTheDocument();
    expect(onIngestionSuccess).toHaveBeenCalledTimes(1);
    expect(onIngestionSuccess).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        source_type: "csv_upload",
      }),
      expect.objectContaining({
        platform: "csv",
        productId: expect.any(String),
      }),
    );

    expect(apiClient.postCsvIngestion).toHaveBeenCalledWith(
      expect.objectContaining({
        source_ref: expect.stringMatching(/^https:\/\/csv\.upload\.local\/[a-f0-9]+$/),
      }),
    );
    expect(apiClient.postEnsureContext).toHaveBeenCalledTimes(1);
  });

  it("handles empty CSV client-side before submit", async () => {
    render(<IngestionPanel />);

    fireEvent.click(screen.getByRole("tab", { name: "Upload CSV" }));
    const emptyFile = new File([""], "empty.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText(/review csv file/i), {
      target: { files: [emptyFile] },
    });

    fireEvent.click(screen.getByRole("button", { name: "Run CSV Ingestion" }));

    expect(await screen.findByText(/csv file is empty/i)).toBeInTheDocument();
    expect(apiClient.postCsvIngestion).not.toHaveBeenCalled();
  });

  it("renders user-friendly CSV backend error message", async () => {
    vi.mocked(apiClient.postCsvIngestion).mockRejectedValueOnce(
      new ApiClientError("Request failed", 400, undefined, {
        detail: "CSV could not be parsed.",
      }),
    );

    render(<IngestionPanel />);

    fireEvent.click(screen.getByRole("tab", { name: "Upload CSV" }));
    const malformedCsv = new File(["body,rating\nvalue\n"], "reviews.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText(/review csv file/i), {
      target: { files: [malformedCsv] },
    });

    fireEvent.click(screen.getByRole("button", { name: "Run CSV Ingestion" }));

    expect(await screen.findByText(/csv could not be parsed/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText(/uploading csv for ingestion and parsing/i)).not.toBeInTheDocument();
    });
  });

  it("shows a helpful message when request times out", async () => {
    const abortError = new Error("aborted");
    abortError.name = "AbortError";
    vi.mocked(apiClient.postUrlIngestion).mockRejectedValueOnce(abortError);

    render(<IngestionPanel />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://www.capterra.com/p/147795/Coveragebook-com/reviews/" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));

    expect(await screen.findByText(/taking longer than expected/i)).toBeInTheDocument();
  });

  it("renders backend failure notices as alerts", async () => {
    vi.mocked(apiClient.postUrlIngestion).mockRejectedValueOnce(
      new ApiClientError("Request failed", 500, {
        error: {
          code: "HTTP_500",
          message: "Ingestion pipeline failed after retries.",
        },
      }),
    );

    render(<IngestionPanel />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://www.capterra.com/p/147795/Coveragebook-com/reviews/" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/ingestion pipeline failed after retries/i);
  });
});
