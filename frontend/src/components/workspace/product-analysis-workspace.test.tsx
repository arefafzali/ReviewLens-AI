import React from "react";
import { render, screen } from "@testing-library/react";

import { ApiClientError, apiClient } from "@/lib/api";

import { ProductAnalysisWorkspace } from "./product-analysis-workspace";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiClient: {
      getProduct: vi.fn(),
      getChatHistory: vi.fn(),
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

describe("ProductAnalysisWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.localStorage.setItem("reviewlens.workspace_id", "workspace-1");

    vi.mocked(apiClient.getChatHistory).mockRejectedValue(
      new ApiClientError("No chat history found.", 404),
    );
  });

  it("loads product-specific summary, suggested questions, and chat shell", async () => {
    vi.mocked(apiClient.getProduct).mockResolvedValue({
      id: "08f51446-b913-4f99-a6cc-0c7f84b49145",
      workspace_id: "workspace-1",
      platform: "capterra",
      name: "PressPage",
      source_url: "https://www.capterra.com/p/164876/PressPage/reviews/",
      stats: {
        suggested_questions: [
          "What themes appear most often?",
          "What are the strongest positive signals?",
        ],
      },
      total_reviews: 12,
      average_rating: 4.25,
      chat_session_count: 1,
      latest_ingestion: {
        ingestion_run_id: "run-123",
        status: "success",
        outcome_code: "ok",
        completed_at: "2026-03-19T10:01:00Z",
      },
      created_at: "2026-03-19T09:59:00Z",
      updated_at: "2026-03-19T10:01:00Z",
    });

    render(<ProductAnalysisWorkspace productId="08f51446-b913-4f99-a6cc-0c7f84b49145" />);

    expect(await screen.findByRole("heading", { name: "Ingestion Summary" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Suggested Questions" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Analyst Chat" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "What themes appear most often?" })).toBeInTheDocument();
  });

  it("renders a clean not-found state when product does not exist", async () => {
    vi.mocked(apiClient.getProduct).mockRejectedValue(
      new ApiClientError("Product not found for workspace.", 404),
    );

    render(<ProductAnalysisWorkspace productId="08f51446-b913-4f99-a6cc-0c7f84b49145" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Product not found for this workspace.");
  });
});
