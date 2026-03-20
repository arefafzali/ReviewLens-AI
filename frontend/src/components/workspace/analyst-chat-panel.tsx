"use client";

import React, { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatCitationItem } from "@/types/api";

export type ChatMessageRole = "user" | "assistant";
export type ChatMessageState = "complete" | "streaming";
export type ChatFinalClassification = "answer" | "out_of_scope" | "insufficient_evidence";

export type ChatMessage = {
  id: string;
  role: ChatMessageRole;
  content: string;
  state?: ChatMessageState;
  finalClassification?: ChatFinalClassification;
  citations?: ChatCitationItem[];
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

type ClassificationPresentation = {
  cardClassName: string;
  badgeClassName: string;
  guidance: string;
};

function classificationPresentation(
  classification: ChatFinalClassification | undefined,
): ClassificationPresentation | null {
  if (classification === "answer") {
    return {
      cardClassName: "border-emerald-300/60 bg-emerald-50/40",
      badgeClassName: "bg-emerald-100 text-emerald-800",
      guidance: "Grounded answer from ingested reviews.",
    };
  }

  if (classification === "out_of_scope") {
    return {
      cardClassName: "border-amber-300/70 bg-amber-50/50",
      badgeClassName: "bg-amber-100 text-amber-900",
      guidance: "Refusal: this question is outside the currently ingested review scope.",
    };
  }

  if (classification === "insufficient_evidence") {
    return {
      cardClassName: "border-sky-300/70 bg-sky-50/50",
      badgeClassName: "bg-sky-100 text-sky-900",
      guidance: "Not enough evidence found in the ingested reviews to answer confidently.",
    };
  }

  return null;
}

function formatCitationRating(value: number | null | undefined): string | null {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return `${value.toFixed(1)} / 5`;
}

function safeCitationText(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim();
}

function CitationList({ citations }: { citations: ChatCitationItem[] }): ReactNode {
  if (citations.length === 0) {
    return null;
  }

  return (
    <section className="mt-3 space-y-2" aria-label="Supporting review evidence">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Supporting review evidence
      </p>
      <ul className="space-y-2">
        {citations.slice(0, 3).map((citation, index) => {
          const rating = formatCitationRating(citation.rating);
          const hasMeta = Boolean(citation.reviewed_at || rating || citation.author_name);
          const evidenceId = safeCitationText(citation.evidence_id) || "E?";
          const reviewId = safeCitationText(citation.review_id) || "unknown-review";
          const title = safeCitationText(citation.title);
          const snippet = safeCitationText(citation.snippet);
          const authorName = safeCitationText(citation.author_name);
          const reviewedAt = safeCitationText(citation.reviewed_at);

          if (!snippet) {
            return null;
          }

          return (
            <li key={`${evidenceId}-${reviewId}-${index}`} className="rounded-md border border-border/70 bg-background/60 p-2">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                  {evidenceId}
                </span>
                {title ? (
                  <span className="truncate text-[11px] text-muted-foreground" title={title}>
                    {title}
                  </span>
                ) : null}
              </div>
              <p className="text-xs text-foreground whitespace-pre-wrap">&quot;{snippet}&quot;</p>
              {hasMeta ? (
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                  {authorName ? <span>{authorName}</span> : null}
                  {reviewedAt ? <span>{reviewedAt}</span> : null}
                  {rating ? <span>{rating}</span> : null}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
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
        const presentation = classificationPresentation(message.finalClassification);
        return (
          <article
            key={message.id}
            className={[
              "rounded-md border p-2",
              isUser ? "border-primary/30 bg-primary/5" : presentation?.cardClassName ?? "border-border/70 bg-muted/20",
            ].join(" ")}
          >
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{roleLabel(message.role)}</p>
              {classification ? (
                <span
                  className={[
                    "rounded-full px-2 py-0.5 text-[11px] font-medium",
                    presentation?.badgeClassName ?? "bg-muted text-muted-foreground",
                  ].join(" ")}
                >
                  {classification}
                </span>
              ) : null}
            </div>
            {isUser ? (
              <p className="text-sm text-foreground whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div className="text-sm text-foreground [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5 [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-muted [&_pre]:p-2 [&_a]:text-primary [&_a]:underline">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: (props) => <a {...props} target="_blank" rel="noreferrer" />,
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
            {!isUser && presentation ? (
              <p className="mt-2 text-xs text-muted-foreground" aria-label="Classification guidance">
                {presentation.guidance}
              </p>
            ) : null}
            {!isUser && message.state !== "streaming" && Array.isArray(message.citations) ? (
              <CitationList citations={message.citations} />
            ) : null}
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
