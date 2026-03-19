"use client";

import React, { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";

export type ChatMessageRole = "user" | "assistant";
export type ChatMessageState = "complete" | "streaming";
export type ChatFinalClassification = "answer" | "out_of_scope" | "insufficient_evidence";

export type ChatMessage = {
  id: string;
  role: ChatMessageRole;
  content: string;
  state?: ChatMessageState;
  finalClassification?: ChatFinalClassification;
};

type AnalystChatPanelProps = {
  messages: ChatMessage[];
  onSubmitQuestion: (question: string) => void | Promise<void>;
  disabled?: boolean;
  isResponding?: boolean;
  onCancelResponse?: () => void;
};

type ChatComposerProps = {
  disabled: boolean;
  isResponding: boolean;
  onSubmitQuestion: (question: string) => void | Promise<void>;
  onCancelResponse?: () => void;
};

function createClientMessageId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const randomHex = Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12);
  return `msg-${randomHex}`;
}

function roleLabel(role: ChatMessageRole): string {
  return role === "user" ? "Analyst" : "Assistant";
}

function classificationLabel(classification: ChatFinalClassification | undefined): string {
  if (classification === "answer") {
    return "Answer";
  }
  if (classification === "out_of_scope") {
    return "Out of scope";
  }
  if (classification === "insufficient_evidence") {
    return "Insufficient evidence";
  }
  return "";
}

function ChatMessageList({ messages, isResponding }: { messages: ChatMessage[]; isResponding: boolean }): ReactNode {
  const endOfListRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const endOfList = endOfListRef.current;
    if (endOfList && typeof endOfList.scrollIntoView === "function") {
      endOfList.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, isResponding]);

  if (messages.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Ask a question about the ingested reviews, or click a suggested question to begin.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {messages.map((message) => {
        const isUser = message.role === "user";
        const classification = classificationLabel(message.finalClassification);
        return (
          <article
            key={message.id}
            className={[
              "rounded-md border p-2",
              isUser ? "border-primary/30 bg-primary/5" : "border-border/70 bg-muted/20",
            ].join(" ")}
          >
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{roleLabel(message.role)}</p>
              {classification ? <span className="text-[11px] text-muted-foreground">{classification}</span> : null}
            </div>
            <p className="text-sm text-foreground whitespace-pre-wrap">{message.content}</p>
            {message.state === "streaming" ? (
              <p className="mt-1 text-[11px] text-muted-foreground" aria-label="Message streaming state">
                Streaming...
              </p>
            ) : null}
          </article>
        );
      })}
      {isResponding ? (
        <article className="rounded-md border border-dashed border-border bg-background p-2" aria-live="polite">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Assistant</p>
          <p className="mt-1 text-sm text-muted-foreground">Analyzing ingested reviews...</p>
        </article>
      ) : null}
      <div ref={endOfListRef} />
    </div>
  );
}

function ChatComposer({ disabled, isResponding, onSubmitQuestion, onCancelResponse }: ChatComposerProps): ReactNode {
  const [draft, setDraft] = useState("");

  function submitQuestion(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || disabled || isResponding) {
      return;
    }

    onSubmitQuestion(trimmed);
    setDraft("");
  }

  return (
    <form className="space-y-2" onSubmit={submitQuestion}>
      <label htmlFor="analyst-chat-question" className="text-sm font-medium text-foreground">
        Ask a question
      </label>
      <textarea
        id="analyst-chat-question"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        rows={3}
        disabled={disabled || isResponding}
        placeholder={disabled ? "Complete ingestion first to unlock chat." : "What are users saying about onboarding?"}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
      />
      <button
        type="submit"
        disabled={disabled || isResponding || draft.trim().length === 0}
        className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isResponding ? "Waiting for response..." : "Submit Question"}
      </button>
      {isResponding ? (
        <button
          type="button"
          onClick={onCancelResponse}
          className="ml-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
        >
          Cancel Response
        </button>
      ) : null}
    </form>
  );
}

export function AnalystChatPanel({
  messages,
  onSubmitQuestion,
  disabled = false,
  isResponding = false,
  onCancelResponse,
}: AnalystChatPanelProps): ReactNode {
  return (
    <div className="space-y-3">
      <div className="max-h-72 overflow-y-auto rounded-md border border-border p-3" aria-label="Analyst chat transcript">
        <ChatMessageList messages={messages} isResponding={isResponding} />
      </div>

      <ChatComposer
        disabled={disabled}
        isResponding={isResponding}
        onSubmitQuestion={onSubmitQuestion}
        onCancelResponse={onCancelResponse}
      />
    </div>
  );
}

export function createUserChatMessage(question: string): ChatMessage {
  return {
    id: createClientMessageId(),
    role: "user",
    content: question,
    state: "complete",
  };
}

export function createStreamingAssistantMessage(): ChatMessage {
  return {
    id: createClientMessageId(),
    role: "assistant",
    content: "",
    state: "streaming",
  };
}
