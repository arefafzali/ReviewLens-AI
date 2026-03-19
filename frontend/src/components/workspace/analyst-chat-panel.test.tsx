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

  it("renders user and assistant messages with classification labels", () => {
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
});
