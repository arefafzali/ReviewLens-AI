import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import { SuggestedQuestions } from "./suggested-questions";

describe("SuggestedQuestions", () => {
  it("renders backend-provided suggestions and handles click", () => {
    const onSelectQuestion = vi.fn();

    render(
      <SuggestedQuestions
        questions={[
          "What do users like most?",
          "What are recurring pain points?",
          "How does onboarding feedback vary?",
        ]}
        hasConversationStarted={false}
        onSelectQuestion={onSelectQuestion}
      />,
    );

    const firstQuestion = screen.getByRole("button", { name: "What do users like most?" });
    fireEvent.click(firstQuestion);

    expect(onSelectQuestion).toHaveBeenCalledTimes(1);
    expect(onSelectQuestion).toHaveBeenCalledWith("What do users like most?");
  });

  it("shows empty state when backend does not provide suggestions", () => {
    render(<SuggestedQuestions questions={[]} hasConversationStarted={false} onSelectQuestion={vi.fn()} />);

    expect(screen.getByText(/No suggested questions are available yet/i)).toBeInTheDocument();
  });

  it("reduces visible suggestions after chat starts and can expand", () => {
    render(
      <SuggestedQuestions
        questions={[
          "What do users like most?",
          "What are recurring pain points?",
          "How does onboarding feedback vary?",
        ]}
        hasConversationStarted={true}
        onSelectQuestion={vi.fn()}
      />,
    );

    expect(screen.getByText(/Conversation started\. Showing top suggestion\./i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "What do users like most?" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "What are recurring pain points?" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Show all/i }));

    expect(screen.getByRole("button", { name: "What are recurring pain points?" })).toBeInTheDocument();
  });
});
