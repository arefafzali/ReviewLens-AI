import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import { AnalystChatPanel } from "./analyst-chat-panel";

describe("AnalystChatPanel", () => {
  it("renders an empty-state transcript hint when no messages exist", () => {
    render(<AnalystChatPanel messages={[]} onSubmitQuestion={vi.fn()} />);

    expect(
      screen.getByText(/ask a question about the ingested reviews, or click a suggested question to begin/i),
    ).toBeInTheDocument();
  });

  it("submits a typed question and clears the composer", () => {
    const onSubmitQuestion = vi.fn();
    render(<AnalystChatPanel messages={[]} onSubmitQuestion={onSubmitQuestion} />);

    const textarea = screen.getByLabelText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: "What do users say about support?" } });

    fireEvent.click(screen.getByRole("button", { name: /submit question/i }));

    expect(onSubmitQuestion).toHaveBeenCalledTimes(1);
    expect(onSubmitQuestion).toHaveBeenCalledWith("What do users say about support?");
    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("renders answer classification with grounded guidance", () => {
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m1",
            role: "user",
            content: "What are the top strengths?",
            state: "complete",
          },
          {
            id: "m2",
            role: "assistant",
            content: "Users most often praise ease of use and responsive support.",
            state: "complete",
            finalClassification: "answer",
          },
        ]}
      />,
    );

    expect(screen.getByText("Analyst")).toBeInTheDocument();
    expect(screen.getByText("Assistant")).toBeInTheDocument();
    expect(screen.getByText("Answer")).toBeInTheDocument();
    expect(screen.getByText(/responsive support/i)).toBeInTheDocument();
    expect(screen.getByText(/grounded answer from ingested reviews/i)).toBeInTheDocument();
  });

  it("renders assistant markdown formatting", () => {
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m-md",
            role: "assistant",
            content: "## Highlights\n\n- **Fast onboarding**\n- [Read source](https://example.com)",
            state: "complete",
            finalClassification: "answer",
          },
        ]}
      />,
    );

    expect(screen.getByRole("heading", { level: 2, name: "Highlights" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Read source" })).toHaveAttribute("href", "https://example.com");
    expect(screen.getByText("Fast onboarding")).toBeInTheDocument();
  });

  it("renders out-of-scope classification distinctly", () => {
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m2",
            role: "assistant",
            content: "I cannot answer this because it is outside the ingested review scope.",
            state: "complete",
            finalClassification: "out_of_scope",
          },
        ]}
      />,
    );

    expect(screen.getByText("Out of scope")).toBeInTheDocument();
    expect(screen.getByText(/outside the currently ingested review scope/i)).toBeInTheDocument();
  });

  it("renders insufficient-evidence classification distinctly", () => {
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m3",
            role: "assistant",
            content: "I need more review evidence before answering this confidently.",
            state: "complete",
            finalClassification: "insufficient_evidence",
          },
        ]}
      />,
    );

    expect(screen.getByText("Insufficient evidence")).toBeInTheDocument();
    expect(screen.getByText(/not enough evidence found in the ingested reviews/i)).toBeInTheDocument();
  });

  it("renders supporting citations with helpful metadata", () => {
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m4",
            role: "assistant",
            content: "Support quality and ease of publishing are repeated strengths.",
            state: "complete",
            finalClassification: "answer",
            citations: [
              {
                evidence_id: "E1",
                review_id: "r1",
                title: "Great support",
                snippet: "The support team was very responsive and patient.",
                author_name: "Alex",
                reviewed_at: "2020-06-30",
                rating: 5,
                rank: 0.93,
              },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByLabelText(/supporting review evidence/i)).toBeInTheDocument();
    expect(screen.getByText("E1")).toBeInTheDocument();
    expect(screen.getByText(/the support team was very responsive and patient/i)).toBeInTheDocument();
    expect(screen.getByText("Alex")).toBeInTheDocument();
    expect(screen.getByText("2020-06-30")).toBeInTheDocument();
    expect(screen.getByText("5.0 / 5")).toBeInTheDocument();
  });

  it("handles sparse citation metadata safely", () => {
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m5",
            role: "assistant",
            content: "Evidence is limited but available.",
            state: "complete",
            finalClassification: "insufficient_evidence",
            citations: [
              {
                evidence_id: "E2",
                review_id: "r2",
                snippet: "Users mention onboarding was simple.",
                rank: 0.51,
              },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByText("E2")).toBeInTheDocument();
    expect(screen.getByText(/users mention onboarding was simple/i)).toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
    expect(screen.queryByText("null")).not.toBeInTheDocument();
  });

  it("renders at most three citations for readability", () => {
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m6",
            role: "assistant",
            content: "Common themes are consistent across evidence.",
            state: "complete",
            finalClassification: "answer",
            citations: [
              { evidence_id: "E1", review_id: "r1", snippet: "Snippet 1", rank: 0.9 },
              { evidence_id: "E2", review_id: "r2", snippet: "Snippet 2", rank: 0.8 },
              { evidence_id: "E3", review_id: "r3", snippet: "Snippet 3", rank: 0.7 },
              { evidence_id: "E4", review_id: "r4", snippet: "Snippet 4", rank: 0.6 },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByText("E1")).toBeInTheDocument();
    expect(screen.getByText("E2")).toBeInTheDocument();
    expect(screen.getByText("E3")).toBeInTheDocument();
    expect(screen.queryByText("E4")).not.toBeInTheDocument();
  });

  it("skips rendering malformed citation snippets", () => {
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m7",
            role: "assistant",
            content: "Evidence is partially available.",
            state: "complete",
            finalClassification: "insufficient_evidence",
            citations: [
              { evidence_id: "E1", review_id: "r1", snippet: "Valid snippet", rank: 0.8 },
              { evidence_id: "E2", review_id: "r2", snippet: "" as never, rank: 0.7 },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByText(/valid snippet/i)).toBeInTheDocument();
    expect(screen.queryByText('""')).not.toBeInTheDocument();
  });

  it("shows loading state and disables composer while responding", () => {
    const onCancelResponse = vi.fn();
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m1",
            role: "user",
            content: "How did sentiment change over time?",
            state: "complete",
          },
        ]}
        isResponding
        onCancelResponse={onCancelResponse}
      />,
    );

    expect(screen.getByText(/analyzing ingested reviews/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /waiting for response/i })).toBeDisabled();
    expect(screen.getByLabelText(/ask a question/i)).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel Response" }));
    expect(onCancelResponse).toHaveBeenCalledTimes(1);
  });

  it("does not render duplicate loading box when a streaming assistant message already exists", () => {
    render(
      <AnalystChatPanel
        onSubmitQuestion={vi.fn()}
        messages={[
          {
            id: "m-stream",
            role: "assistant",
            content: "",
            state: "streaming",
          },
        ]}
        isResponding
      />,
    );

    expect(screen.queryByText(/analyzing ingested reviews/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/message streaming state/i)).toBeInTheDocument();
  });

  it("submits the question when pressing Enter", () => {
    const onSubmitQuestion = vi.fn();
    render(<AnalystChatPanel messages={[]} onSubmitQuestion={onSubmitQuestion} />);

    const textarea = screen.getByLabelText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: "What changed in sentiment this month?" } });
    fireEvent.keyDown(textarea, { key: "Enter", code: "Enter", charCode: 13 });

    expect(onSubmitQuestion).toHaveBeenCalledTimes(1);
    expect(onSubmitQuestion).toHaveBeenCalledWith("What changed in sentiment this month?");
    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("keeps multiline editing when pressing Shift+Enter", () => {
    const onSubmitQuestion = vi.fn();
    render(<AnalystChatPanel messages={[]} onSubmitQuestion={onSubmitQuestion} />);

    const textarea = screen.getByLabelText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: "Line one" } });
    fireEvent.keyDown(textarea, { key: "Enter", code: "Enter", charCode: 13, shiftKey: true });

    expect(onSubmitQuestion).not.toHaveBeenCalled();
  });
});
