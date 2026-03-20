"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import {
  AnalystChatPanel,
  createStreamingAssistantMessage,
  createUserChatMessage,
  type ChatMessage,
} from "@/components/workspace/analyst-chat-panel";
import { IngestionSummaryDashboard } from "@/components/workspace/ingestion-summary-dashboard";
import { SuggestedQuestions } from "@/components/workspace/suggested-questions";
import { ApiClientError, apiClient } from "@/lib/api";
import { ChatStreamTransportError, streamChatCompletion } from "@/lib/chat-stream";
import {
  getStoredChatSessionId,
  getWorkspaceContextIds,
  setActiveProductId,
  setStoredChatSessionId,
} from "@/lib/workspace-context";
import type {
  ChatCitationItem,
  IngestionAttemptResponse,
  IngestionOutcomeCode,
  IngestionRunStatus,
  ProductDetailResponse,
} from "@/types/api";

type WorkspaceSection = {
  id: string;
  title: string;
  description: string;
  status: "loading" | "ready";
  placeholder: ReactNode;
};

type ProductAnalysisWorkspaceProps = {
  productId: string;
};

function parseClassification(value: unknown): ChatMessage["finalClassification"] | undefined {
  if (value === "answer" || value === "out_of_scope" || value === "insufficient_evidence") {
    return value;
  }
  return undefined;
}

function parseCitations(value: unknown): ChatCitationItem[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const citations: ChatCitationItem[] = [];
  value.forEach((item) => {
    if (!item || typeof item !== "object") {
      return;
    }

    const candidate = item as Partial<ChatCitationItem>;
    const evidenceId = typeof candidate.evidence_id === "string" ? candidate.evidence_id : "";
    const snippet = typeof candidate.snippet === "string" ? candidate.snippet : "";
    if (!evidenceId || !snippet) {
      return;
    }

    citations.push({
      evidence_id: evidenceId,
      review_id: typeof candidate.review_id === "string" ? candidate.review_id : "",
      title: typeof candidate.title === "string" ? candidate.title : null,
      snippet,
      author_name: typeof candidate.author_name === "string" ? candidate.author_name : null,
      reviewed_at: typeof candidate.reviewed_at === "string" ? candidate.reviewed_at : null,
      rating: typeof candidate.rating === "number" ? candidate.rating : null,
      rank: typeof candidate.rank === "number" ? candidate.rank : 0,
    });
  });

  return citations;
}

function parseRunStatus(value: unknown): IngestionRunStatus {
  if (value === "running" || value === "success" || value === "partial" || value === "failed") {
    return value;
  }
  return "success";
}

function parseOutcomeCode(value: unknown): IngestionOutcomeCode {
  if (
    value === "ok" ||
    value === "low_data" ||
    value === "blocked" ||
    value === "parse_failed" ||
    value === "unsupported_source" ||
    value === "invalid_url" ||
    value === "empty_csv" ||
    value === "malformed_csv"
  ) {
    return value;
  }
  return "ok";
}

function parseSuggestedQuestionsFromStats(stats: Record<string, unknown>): string[] {
  const raw = stats.suggested_questions;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function buildIngestionSnapshotFromProduct(detail: ProductDetailResponse): IngestionAttemptResponse | null {
  const hasIngestion = Boolean(detail.latest_ingestion?.ingestion_run_id) || detail.total_reviews > 0;
  if (!hasIngestion) {
    return null;
  }

  const stats = detail.stats ?? {};
  const normalizedStats = typeof stats === "object" && stats ? stats : {};

  return {
    ingestion_run_id: detail.latest_ingestion?.ingestion_run_id ?? `product-${detail.id}`,
    source_type: "scrape",
    status: parseRunStatus(detail.latest_ingestion?.status),
    outcome_code: parseOutcomeCode(detail.latest_ingestion?.outcome_code),
    captured_reviews: detail.total_reviews,
    message: "Loaded latest product snapshot.",
    warnings: [],
    diagnostics: {},
    summary_snapshot: {
      ...normalizedStats,
      total_reviews: detail.total_reviews,
      average_rating: detail.average_rating ?? null,
      suggested_questions: parseSuggestedQuestionsFromStats(detail.stats),
    },
    started_at: detail.latest_ingestion?.completed_at ?? null,
    completed_at: detail.latest_ingestion?.completed_at ?? null,
  };
}

function SectionStatusBadge({ status }: { status: "loading" | "ready" }): ReactNode {
  if (status === "ready") {
    return (
      <span className="inline-flex rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
        Ready
      </span>
    );
  }

  return (
    <span className="inline-flex rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
      Loading
    </span>
  );
}

function WorkspaceSectionCard({ section }: { section: WorkspaceSection }): ReactNode {
  return (
    <section aria-labelledby={section.id} className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 id={section.id} className="text-base font-semibold tracking-tight">
            {section.title}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">{section.description}</p>
        </div>
        <SectionStatusBadge status={section.status} />
      </div>
      {section.placeholder}
    </section>
  );
}

export function ProductAnalysisWorkspace({ productId }: ProductAnalysisWorkspaceProps): ReactNode {
  const { workspaceId } = getWorkspaceContextIds();

  const [product, setProduct] = useState<ProductDetailResponse | null>(null);
  const [latestIngestion, setLatestIngestion] = useState<IngestionAttemptResponse | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isChatResponding, setIsChatResponding] = useState(false);
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const activeStreamControllerRef = useRef<AbortController | null>(null);
  const streamEpochRef = useRef(0);
  const productIdRef = useRef(productId);

  const suggestedQuestions = latestIngestion?.summary_snapshot?.suggested_questions ?? [];
  const hasConversationStarted = chatMessages.length > 0;
  const canAnalyzeProduct = Boolean(latestIngestion) || (product?.total_reviews ?? 0) > 0 || chatMessages.length > 0;

  useEffect(() => {
    productIdRef.current = productId;
  }, [productId]);

  useEffect(() => {
    let canceled = false;
    setActiveProductId(workspaceId, productId);
    setLoadError(null);
    streamEpochRef.current += 1;
    activeStreamControllerRef.current?.abort();
    activeStreamControllerRef.current = null;
    setIsChatResponding(false);
    setChatMessages([]);
    setChatSessionId(null);

    const storedSessionId = getStoredChatSessionId(workspaceId, productId) ?? undefined;

    void apiClient
      .getProduct(workspaceId, productId)
      .then((detail) => {
        if (canceled) {
          return;
        }
        setProduct(detail);
        setLatestIngestion(buildIngestionSnapshotFromProduct(detail));
      })
      .catch((error: unknown) => {
        if (canceled) {
          return;
        }

        if (error instanceof ApiClientError && error.status === 404) {
          setLoadError("Product not found for this workspace.");
          return;
        }

        setLoadError("Unable to load product analysis right now.");
      });

    void apiClient
      .getChatHistory(workspaceId, productId, storedSessionId)
      .then((history) => {
        if (canceled) {
          return;
        }

        setChatSessionId(history.chat_session_id);
        setStoredChatSessionId(workspaceId, productId, history.chat_session_id);
        setChatMessages(
          history.messages.map((item) => {
            const metadata = item.metadata ?? {};
            return {
              id: `persisted-${history.chat_session_id}-${item.message_index}`,
              role: item.role,
              content: item.content,
              state: "complete",
              finalClassification:
                parseClassification((metadata as Record<string, unknown>).classification) ??
                (item.is_refusal ? "out_of_scope" : undefined),
              citations: parseCitations((metadata as Record<string, unknown>).citations),
            };
          }),
        );
      })
      .catch((error: unknown) => {
        if (canceled) {
          return;
        }

        if (error instanceof ApiClientError && error.status === 404) {
          return;
        }
      });

    return () => {
      canceled = true;
    };
  }, [workspaceId, productId]);

  const appendTokenToMessage = useCallback((messageId: string, token: string) => {
    setChatMessages((previous) =>
      previous.map((message) => {
        if (message.id !== messageId) {
          return message;
        }

        return {
          ...message,
          content: `${message.content}${token}`,
        };
      }),
    );
  }, []);

  const finalizeAssistantMessage = useCallback(
    (messageId: string, payload: { content: string; citations?: ChatCitationItem[]; classification?: ChatMessage["finalClassification"] }) => {
      setChatMessages((previous) =>
        previous.map((message) => {
          if (message.id !== messageId) {
            return message;
          }

          return {
            ...message,
            content: payload.content,
            state: "complete",
            finalClassification: payload.classification,
            citations: payload.citations ?? [],
          };
        }),
      );
    },
    [],
  );

  async function appendQuestionToChat(question: string): Promise<void> {
    if (!canAnalyzeProduct || isChatResponding) {
      return;
    }

    const userMessage = createUserChatMessage(question);
    const assistantMessage = createStreamingAssistantMessage();
    const assistantMessageId = assistantMessage.id;

    setChatMessages((previous) => [...previous, userMessage, assistantMessage]);
    setIsChatResponding(true);

    const controller = new AbortController();
    activeStreamControllerRef.current = controller;
    const streamEpoch = ++streamEpochRef.current;
    const streamProductId = productId;

    function isActiveStream(): boolean {
      return streamEpochRef.current === streamEpoch && streamProductId === productIdRef.current;
    }

    try {
      const done = await streamChatCompletion({
        payload: {
          workspace_id: workspaceId,
          product_id: productId,
          question,
          ...(chatSessionId ? { chat_session_id: chatSessionId } : {}),
        },
        signal: controller.signal,
        onMeta: (meta) => {
          if (!isActiveStream()) {
            return;
          }
          setChatSessionId(meta.chat_session_id);
          setStoredChatSessionId(workspaceId, productId, meta.chat_session_id);
        },
        onToken: ({ text }) => {
          if (!isActiveStream()) {
            return;
          }
          appendTokenToMessage(assistantMessageId, text);
        },
        onDone: (payload) => {
          if (!isActiveStream()) {
            return;
          }
          setChatSessionId(payload.chat_session_id);
          setStoredChatSessionId(workspaceId, productId, payload.chat_session_id);
          finalizeAssistantMessage(assistantMessageId, {
            content: payload.answer,
            citations: payload.citations,
            classification: payload.classification,
          });
        },
      });

      if (!isActiveStream()) {
        return;
      }

      finalizeAssistantMessage(assistantMessageId, {
        content: done.answer,
        citations: done.citations,
        classification: done.classification,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        finalizeAssistantMessage(assistantMessageId, {
          content: "Response canceled by analyst.",
          classification: "insufficient_evidence",
        });
      } else if (error instanceof ChatStreamTransportError) {
        finalizeAssistantMessage(assistantMessageId, {
          content: error.message || "Chat streaming failed.",
          classification: "insufficient_evidence",
        });
      } else if (error instanceof Error) {
        finalizeAssistantMessage(assistantMessageId, {
          content: error.message || "Chat streaming failed.",
          classification: "insufficient_evidence",
        });
      } else {
        finalizeAssistantMessage(assistantMessageId, {
          content: "Unable to complete this response right now. Please retry.",
          classification: "insufficient_evidence",
        });
      }
    } finally {
      if (activeStreamControllerRef.current === controller) {
        activeStreamControllerRef.current = null;
      }
      if (isActiveStream()) {
        setIsChatResponding(false);
      }
    }
  }

  function cancelActiveResponse(): void {
    activeStreamControllerRef.current?.abort();
  }

  if (loadError) {
    return (
      <div className="rounded-md border border-border bg-card p-5">
        <p className="text-sm text-foreground" role="alert">{loadError}</p>
      </div>
    );
  }

  const summarySection: WorkspaceSection = {
    id: "ingestion-summary",
    title: "Ingestion Summary",
    description: "Show outcome, capture counts, analytics highlights, and extraction diagnostics.",
    status: latestIngestion ? "ready" : "loading",
    placeholder: latestIngestion ? <IngestionSummaryDashboard result={latestIngestion} /> : (
      <div className="grid gap-2 sm:grid-cols-3">
        <div className="h-14 animate-pulse rounded-md bg-muted" />
        <div className="h-14 animate-pulse rounded-md bg-muted" />
        <div className="h-14 animate-pulse rounded-md bg-muted" />
      </div>
    ),
  };

  const analystChatSection: WorkspaceSection = {
    id: "analyst-chat",
    title: "Analyst Chat",
    description: "Start with grounded prompts, then continue with scoped multi-turn Q&A.",
    status: canAnalyzeProduct ? "ready" : "loading",
    placeholder: canAnalyzeProduct ? (
      <div className="space-y-4">
        <section className="rounded-md border border-border bg-muted/20 p-3" aria-label="Suggested prompts for chat">
          <h3 className="text-sm font-semibold text-foreground">Suggested Questions</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Use these grounded prompts to start analysis quickly, then branch into follow-up questions.
          </p>
          <div className="mt-3">
            <SuggestedQuestions
              questions={suggestedQuestions}
              hasConversationStarted={hasConversationStarted}
              onSelectQuestion={appendQuestionToChat}
            />
          </div>
        </section>

        <AnalystChatPanel
          messages={chatMessages}
          onSubmitQuestion={appendQuestionToChat}
          disabled={false}
          isResponding={isChatResponding}
          onCancelResponse={cancelActiveResponse}
        />
      </div>
    ) : (
      <div className="space-y-3">
        <div className="h-20 animate-pulse rounded-md bg-muted" />
        <div className="h-24 animate-pulse rounded-md bg-muted" />
        <div className="h-24 animate-pulse rounded-md bg-muted" />
        <div className="h-10 animate-pulse rounded-md bg-muted" />
      </div>
    ),
  };

  return (
    <div className="space-y-4">
      <WorkspaceSectionCard key={summarySection.id} section={summarySection} />
      <WorkspaceSectionCard key={analystChatSection.id} section={analystChatSection} />
    </div>
  );
}
