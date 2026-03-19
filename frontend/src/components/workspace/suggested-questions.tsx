"use client";

import React, { useMemo, useState } from "react";
import type { ReactNode } from "react";

type SuggestedQuestionsProps = {
  questions: string[];
  hasConversationStarted: boolean;
  onSelectQuestion: (question: string) => void;
  maxQuestions?: number;
};

const DEFAULT_MAX_QUESTIONS = 5;

export function SuggestedQuestions({
  questions,
  hasConversationStarted,
  onSelectQuestion,
  maxQuestions = DEFAULT_MAX_QUESTIONS,
}: SuggestedQuestionsProps): ReactNode {
  const [showAllAfterChatStart, setShowAllAfterChatStart] = useState(false);

  const trimmedQuestions = useMemo(
    () => questions.map((item) => item.trim()).filter((item) => item.length > 0).slice(0, maxQuestions),
    [questions, maxQuestions],
  );

  if (trimmedQuestions.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
        No suggested questions are available yet. Complete ingestion to generate grounded starter prompts.
      </p>
    );
  }

  const reducedMode = hasConversationStarted && !showAllAfterChatStart;
  const visibleQuestions = reducedMode ? trimmedQuestions.slice(0, 1) : trimmedQuestions;

  return (
    <div className="space-y-3">
      {reducedMode ? (
        <div className="flex items-center justify-between gap-2 rounded-md border border-border/70 bg-muted/30 px-3 py-2">
          <p className="text-xs text-muted-foreground">Conversation started. Showing top suggestion.</p>
          <button
            type="button"
            onClick={() => setShowAllAfterChatStart(true)}
            className="text-xs font-medium text-foreground underline underline-offset-2"
          >
            Show all
          </button>
        </div>
      ) : null}

      <ul className="space-y-2" aria-label="Suggested questions list">
        {visibleQuestions.map((question) => (
          <li key={question}>
            <button
              type="button"
              onClick={() => onSelectQuestion(question)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-left text-sm text-foreground transition hover:bg-muted"
            >
              {question}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
