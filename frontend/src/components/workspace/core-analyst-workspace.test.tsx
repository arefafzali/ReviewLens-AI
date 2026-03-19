import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ApiClientError, apiClient } from "@/lib/api";
import { ChatStreamTransportError, streamChatCompletion } from "@/lib/chat-stream";

import { CoreAnalystWorkspace } from "./core-analyst-workspace";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiClient: {
      postEnsureContext: vi.fn(),
      postUrlIngestion: vi.fn(),
      postCsvIngestion: vi.fn(),
      getChatHistory: vi.fn(),
      getProducts: vi.fn(),
      getProduct: vi.fn(),
      deleteProduct: vi.fn(),
    },
  };
});

vi.mock("@/lib/chat-stream", async () => {
  const actual = await vi.importActual<typeof import("@/lib/chat-stream")>("@/lib/chat-stream");
  return {
    ...actual,
    streamChatCompletion: vi.fn(),
  };
});

function mockSuccessfulIngestion() {
  vi.mocked(apiClient.postEnsureContext).mockResolvedValue({
    workspace_id: "workspace-1",
    product_id: "product-1",
    created_workspace: false,
    created_product: false,
  });
  vi.mocked(apiClient.postUrlIngestion).mockResolvedValue({
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
}

describe("CoreAnalystWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.localStorage.setItem("reviewlens.workspace_id", "workspace-1");
    window.localStorage.setItem("reviewlens.active_product_id.workspace-1", "product-1");

    vi.mocked(apiClient.getProducts).mockResolvedValue([
      {
        id: "product-1",
        workspace_id: "workspace-1",
        platform: "generic",
        name: "Example Product",
        source_url: "https://www.g2.com/products/example/reviews",
        total_reviews: 12,
        average_rating: 4.25,
        chat_session_count: 1,
        latest_ingestion: {
          ingestion_run_id: "run-456",
          status: "success",
          outcome_code: "ok",
          completed_at: "2026-03-19T10:01:00Z",
        },
        updated_at: "2026-03-19T10:01:00Z",
      },
    ]);
    vi.mocked(apiClient.getProduct).mockResolvedValue({
      id: "product-1",
      workspace_id: "workspace-1",
      platform: "generic",
      external_product_id: null,
      name: "Example Product",
      source_url: "https://www.g2.com/products/example/reviews",
      stats: {
        suggested_questions: [
          "What themes appear most often?",
          "What are the top strengths users mention?",
          "Which concerns appear in lower-rated reviews?",
        ],
      },
      total_reviews: 12,
      average_rating: 4.25,
      chat_session_count: 1,
      latest_ingestion: {
        ingestion_run_id: "run-456",
        status: "success",
        outcome_code: "ok",
        completed_at: "2026-03-19T10:01:00Z",
      },
      created_at: "2026-03-19T09:59:00Z",
      updated_at: "2026-03-19T10:01:00Z",
    });
    mockSuccessfulIngestion();
    vi.mocked(apiClient.deleteProduct).mockResolvedValue();
    vi.mocked(apiClient.getChatHistory).mockRejectedValue(
      new ApiClientError("No chat history found.", 404),
    );
  });

  it("optimistically prepends a newly ingested product without full reload", async () => {
    vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValueOnce("product-new");

    vi.mocked(apiClient.getProducts)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          id: "product-new",
          workspace_id: "workspace-1",
          platform: "generic",
          name: "new product",
          source_url: "https://www.g2.com/products/new-product/reviews",
          total_reviews: 3,
          average_rating: 4.1,
          chat_session_count: 0,
          latest_ingestion: {
            ingestion_run_id: "run-new",
            status: "success",
            outcome_code: "ok",
            completed_at: "2026-03-19T10:01:00Z",
          },
          updated_at: "2026-03-19T10:01:00Z",
        },
      ]);
    vi.mocked(apiClient.getProduct).mockRejectedValue(new ApiClientError("Product not found.", 404));
    vi.mocked(apiClient.postUrlIngestion).mockResolvedValueOnce({
      ingestion_run_id: "run-new",
      source_type: "scrape",
      status: "success",
      outcome_code: "ok",
      captured_reviews: 3,
      message: "Ingestion completed successfully.",
      warnings: [],
      diagnostics: {},
      summary_snapshot: {
        total_reviews: 3,
        average_rating: 4.1,
      },
      started_at: "2026-03-19T10:00:00Z",
      completed_at: "2026-03-19T10:01:00Z",
    });

    render(<CoreAnalystWorkspace />);

    expect(await screen.findByText(/no products yet/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://www.g2.com/products/new-product/reviews" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));

    expect(await screen.findByText("run-new")).toBeInTheDocument();
    expect(await screen.findByText("new product")).toBeInTheDocument();
    expect(await screen.findByText(/ingestion complete\. product list updated\./i)).toBeInTheDocument();
    expect(vi.mocked(apiClient.getProducts).mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("optimistically removes a product and rolls back when delete fails", async () => {
    vi.mocked(apiClient.deleteProduct).mockRejectedValueOnce(
      new ApiClientError("Delete failed", 500),
    );

    render(<CoreAnalystWorkspace />);

    expect(await screen.findByText("Example Product")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /delete product example product/i }));

    await waitFor(() => {
      expect(screen.queryByText("Example Product")).not.toBeInTheDocument();
    });

    expect(await screen.findByText(/could not delete example product\. restored product list\./i)).toBeInTheDocument();
    expect(await screen.findByText("Example Product")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() => {
      expect(screen.queryByText(/could not delete example product\. restored product list\./i)).not.toBeInTheDocument();
    });
  });

  it("hydrates persisted chat history on workspace re-entry without duplicates", async () => {
    vi.mocked(apiClient.getChatHistory).mockResolvedValueOnce({
      chat_session_id: "session-h1",
      messages: [
        {
          message_index: 1,
          role: "user",
          content: "What are common strengths?",
          is_refusal: false,
          metadata: {},
        },
        {
          message_index: 2,
          role: "assistant",
          content: "Support responsiveness and ease of use are common strengths.",
          is_refusal: false,
          metadata: {
            classification: "answer",
            citations: [
              {
                evidence_id: "E1",
                review_id: "review-1",
                snippet: "Support was responsive and onboarding was simple.",
                rank: 0.93,
              },
            ],
          },
        },
      ],
    });

    render(<CoreAnalystWorkspace />);

    expect(await screen.findByText("What are common strengths?")).toBeInTheDocument();
    expect(await screen.findByText("Support responsiveness and ease of use are common strengths.")).toBeInTheDocument();
    expect(await screen.findByText("E1")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Analyst Chat" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://www.g2.com/products/example/reviews" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));
    await screen.findByText("run-456");

    await waitFor(() => {
      expect(screen.queryByText("What are common strengths?")).not.toBeInTheDocument();
    });
    expect(vi.mocked(apiClient.getChatHistory).mock.calls.length).toBeGreaterThanOrEqual(1);
  });

  it("updates ingestion summary section and streams assistant response", async () => {
    vi.mocked(streamChatCompletion).mockImplementationOnce(async ({ onMeta, onToken, onDone }) => {
      onMeta?.({
        chat_session_id: "session-1",
        provider: "fake",
        history_message_count: 0,
      });
      onToken?.({ text: "Question queued " });
      onToken?.({ text: "for analysis." });
      onDone?.({
        classification: "answer",
        chat_session_id: "session-1",
        citations: [
          {
            evidence_id: "E1",
            review_id: "review-1",
            title: "Fast onboarding",
            snippet: "Onboarding was fast and support was helpful.",
            author_name: "Ari",
            reviewed_at: "2026-03-10",
            rating: 4.8,
            rank: 0.95,
          },
        ],
        answer: "Question queued for analysis.",
      });
      return {
        classification: "answer",
        chat_session_id: "session-1",
        citations: [
          {
            evidence_id: "E1",
            review_id: "review-1",
            title: "Fast onboarding",
            snippet: "Onboarding was fast and support was helpful.",
            author_name: "Ari",
            reviewed_at: "2026-03-10",
            rating: 4.8,
            rank: 0.95,
          },
        ],
        answer: "Question queued for analysis.",
      };
    });

    render(<CoreAnalystWorkspace />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://www.g2.com/products/example/reviews" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));

    expect(await screen.findByText("run-456")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Ingestion Summary" })).toBeInTheDocument();
    expect((await screen.findAllByText("4.25 / 5")).length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText("support (5)")).toBeInTheDocument();
    expect(await screen.findByText("2026-03-10 to 2026-03-12")).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: "What themes appear most often?" }));

    expect(await screen.findByText("Question queued for analysis.")).toBeInTheDocument();
    expect(await screen.findByLabelText(/supporting review evidence/i)).toBeInTheDocument();
    expect(await screen.findByText("E1")).toBeInTheDocument();
    expect(await screen.findByText("Ari")).toBeInTheDocument();
    expect(await screen.findByText("Analyst")).toBeInTheDocument();
    expect(await screen.findByText("Assistant")).toBeInTheDocument();
    expect(await screen.findByText(/Conversation started\. Showing top suggestion\./i)).toBeInTheDocument();
    await waitFor(() => {
      expect(streamChatCompletion).toHaveBeenCalledTimes(1);
    });
  });

  it("cancels active streaming response", async () => {
    vi.mocked(streamChatCompletion).mockImplementationOnce(({ signal }) => {
      return new Promise((_, reject) => {
        signal?.addEventListener("abort", () => {
          reject(new DOMException("Chat stream aborted.", "AbortError"));
        });
      });
    });

    render(<CoreAnalystWorkspace />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://www.g2.com/products/example/reviews" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));
    await screen.findByText("run-456");

    fireEvent.change(screen.getByLabelText(/ask a question/i), {
      target: { value: "What do users mention most often?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit Question" }));

    expect(await screen.findByRole("button", { name: "Cancel Response" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel Response" }));

    await waitFor(() => {
      expect(screen.getByText("Response canceled by analyst.")).toBeInTheDocument();
    });
  });

  it("surfaces backend stream errors instead of generic fallback text", async () => {
    vi.mocked(streamChatCompletion).mockRejectedValueOnce(
      new ChatStreamTransportError("OpenAI request timed out while generating response."),
    );

    render(<CoreAnalystWorkspace />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://www.g2.com/products/example/reviews" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run URL Ingestion" }));
    await screen.findByText("run-456");

    fireEvent.change(screen.getByLabelText(/ask a question/i), {
      target: { value: "What reasons in the reviews best explain the average rating?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit Question" }));

    await waitFor(() => {
      expect(screen.getByText("OpenAI request timed out while generating response.")).toBeInTheDocument();
    });
  });
});
