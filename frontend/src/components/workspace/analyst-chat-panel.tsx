"use client";

import React, { useState } from "react";
import type { FormEvent, ReactNode } from "react";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type AnalystChatPanelProps = {
  messages: ChatMessage[];
  onSubmitQuestion: (question: string) => void;
  disabled?: boolean;
};

function createClientMessageId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const randomHex = Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12);
  return `msg-${randomHex}`;
}

export function AnalystChatPanel({ messages, onSubmitQuestion, disabled = false }: AnalystChatPanelProps): ReactNode {
  const [draft, setDraft] = useState("");

  function submitQuestion(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || disabled) {
      return;
    }

    onSubmitQuestion(trimmed);
    setDraft("");
  }

  return (
    <div className="space-y-3">
      <div className="max-h-64 space-y-2 overflow-y-auto rounded-md border border-border p-3" aria-label="Analyst chat transcript">
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Ask a question about the ingested reviews, or click a suggested question to begin.
          </p>
        ) : (
          messages.map((message) => (
            <article key={message.id} className="rounded-md border border-border/70 bg-muted/20 p-2">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{message.role}</p>
              <p className="text-sm text-foreground">{message.content}</p>
            </article>
          ))
        )}
      </div>

      <form className="space-y-2" onSubmit={submitQuestion}>
        <label htmlFor="analyst-chat-question" className="text-sm font-medium text-foreground">
          Ask a question
        </label>
        <textarea
          id="analyst-chat-question"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={3}
          disabled={disabled}
          placeholder={disabled ? "Complete ingestion first to unlock chat." : "What are users saying about onboarding?"}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={disabled || draft.trim().length === 0}
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Submit Question
        </button>
      </form>
    </div>
  );
}

export function buildChatMessagesForQuestion(question: string): ChatMessage[] {
  const userMessage: ChatMessage = {
    id: createClientMessageId(),
    role: "user",
    content: question,
  };

  const assistantMessage: ChatMessage = {
    id: createClientMessageId(),
    role: "assistant",
    content: "Question queued for grounded chat analysis.",
  };

  return [userMessage, assistantMessage];
}
