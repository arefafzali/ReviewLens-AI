"use client";

import React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { ProductCard } from "@/components/dashboard/product-card";
import {
  AnalystChatPanel,
  createStreamingAssistantMessage,
  createUserChatMessage,
  type ChatMessage,
} from "@/components/workspace/analyst-chat-panel";
import { ApiClientError, apiClient } from "@/lib/api";
import { ChatStreamTransportError, streamChatCompletion } from "@/lib/chat-stream";
import {
  getStoredChatSessionId,
  getWorkspaceContextIds,
  setActiveProductId,
  setStoredChatSessionId,
} from "@/lib/workspace-context";
import { IngestionPanel } from "@/components/workspace/ingestion-panel";
import { IngestionSummaryDashboard } from "@/components/workspace/ingestion-summary-dashboard";
import { SuggestedQuestions } from "@/components/workspace/suggested-questions";
import type { ChatCitationItem, IngestionAttemptResponse, IngestionOutcomeCode, IngestionRunStatus, ProductDetailResponse, ProductListItem } from "@/types/api";

type SectionStatus = "loading" | "ready";

type WorkspaceSection = {
  id: string;
  title: string;
  description: string;
  status: SectionStatus;
  placeholder: ReactNode;
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

  return value
    .filter((item): item is ChatCitationItem => Boolean(item && typeof item === "object" && "evidence_id" in item && "snippet" in item))
    .map((item) => ({
      ...item,
      rank: typeof item.rank === "number" ? item.rank : 0,
    }));
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
      total_reviews: detail.total_reviews,
      average_rating: detail.average_rating ?? null,
      suggested_questions: parseSuggestedQuestionsFromStats(detail.stats),
    },
    started_at: detail.latest_ingestion?.completed_at ?? null,
    completed_at: detail.latest_ingestion?.completed_at ?? null,
  };
}

function SectionStatusBadge({ status }: { status: SectionStatus }): ReactNode {
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

export function CoreAnalystWorkspace(): ReactNode {
  const initialContext = getWorkspaceContextIds();
  const workspaceId = initialContext.workspaceId;

  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [isProductsLoading, setIsProductsLoading] = useState(true);
  const [selectedProductId, setSelectedProductId] = useState<string>(initialContext.productId);
  const [latestIngestion, setLatestIngestion] = useState<IngestionAttemptResponse | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isChatResponding, setIsChatResponding] = useState(false);
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);

  const activeStreamControllerRef = useRef<AbortController | null>(null);
  const selectedProduct = products.find((item) => item.id === selectedProductId) ?? null;
  const canAnalyzeSelectedProduct = Boolean(latestIngestion) || (selectedProduct?.total_reviews ?? 0) > 0 || chatMessages.length > 0;

  const suggestedQuestions = latestIngestion?.summary_snapshot?.suggested_questions ?? [];
  const hasConversationStarted = chatMessages.length > 0;

  const loadProducts = useCallback(async () => {
    try {
      const items = await apiClient.getProducts(workspaceId);
      setProducts(items);
      setSelectedProductId((previous) => {
        if (items.some((item) => item.id === previous)) {
          return previous;
        }
        if (!previous && items.length > 0) {
          return items[0].id;
        }
        return previous;
      });
    } catch {
      setProducts([]);
    } finally {
      setIsProductsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    setActiveProductId(workspaceId, selectedProductId);
  }, [workspaceId, selectedProductId]);

  useEffect(() => {
    let canceled = false;
    const storedSessionId = getStoredChatSessionId(workspaceId, selectedProductId) ?? undefined;

    activeStreamControllerRef.current?.abort();
    activeStreamControllerRef.current = null;
    setIsChatResponding(false);
    setChatMessages([]);
    setChatSessionId(null);

    if (!selectedProductId) {
      return () => {
        canceled = true;
      };
    }

    void apiClient
      .getProduct(workspaceId, selectedProductId)
      .then((productDetail) => {
        if (canceled) {
          return;
        }
        const snapshot = buildIngestionSnapshotFromProduct(productDetail);
        setLatestIngestion((previous) => {
          if (!snapshot) {
            return null;
          }

          if (
            previous &&
            previous.ingestion_run_id === snapshot.ingestion_run_id &&
            Object.keys(previous.summary_snapshot ?? {}).length > Object.keys(snapshot.summary_snapshot ?? {}).length
          ) {
            return previous;
          }

          return snapshot;
        });
      })
      .catch((error: unknown) => {
        if (canceled) {
          return;
        }
        if (error instanceof ApiClientError && error.status === 404) {
          setLatestIngestion(null);
          return;
        }
      });

    void apiClient
      .getChatHistory(workspaceId, selectedProductId, storedSessionId)
      .then((history) => {
        if (canceled) {
          return;
        }

        setChatSessionId(history.chat_session_id);
        setStoredChatSessionId(workspaceId, selectedProductId, history.chat_session_id);

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
  }, [workspaceId, selectedProductId]);

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
    if (!selectedProductId || !canAnalyzeSelectedProduct || isChatResponding) {
      return;
    }

    const userMessage = createUserChatMessage(question);
    const assistantMessage = createStreamingAssistantMessage();
    const assistantMessageId = assistantMessage.id;

    setChatMessages((previous) => [...previous, userMessage, assistantMessage]);
    setIsChatResponding(true);

    const controller = new AbortController();
    activeStreamControllerRef.current = controller;

    try {
      const done = await streamChatCompletion({
        payload: {
          workspace_id: workspaceId,
          product_id: selectedProductId,
          question,
          ...(chatSessionId ? { chat_session_id: chatSessionId } : {}),
        },
        signal: controller.signal,
        onMeta: (meta) => {
          setChatSessionId(meta.chat_session_id);
          setStoredChatSessionId(workspaceId, selectedProductId, meta.chat_session_id);
        },
        onToken: ({ text }) => {
          appendTokenToMessage(assistantMessageId, text);
        },
        onDone: (payload) => {
          setChatSessionId(payload.chat_session_id);
          setStoredChatSessionId(workspaceId, selectedProductId, payload.chat_session_id);
          finalizeAssistantMessage(assistantMessageId, {
            content: payload.answer,
            citations: payload.citations,
            classification: payload.classification,
          });
        },
      });

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
      setIsChatResponding(false);
    }
  }

  function cancelActiveResponse(): void {
    activeStreamControllerRef.current?.abort();
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

  const suggestedQuestionsSection: WorkspaceSection = {
    id: "suggested-questions",
    title: "Suggested Questions",
    description: "Display grounded starter prompts generated from ingested reviews.",
    status: latestIngestion ? "ready" : "loading",
    placeholder: latestIngestion ? (
      <SuggestedQuestions
        questions={suggestedQuestions}
        hasConversationStarted={hasConversationStarted}
        onSelectQuestion={appendQuestionToChat}
      />
    ) : (
      <ul className="space-y-2">
        <li className="h-8 animate-pulse rounded-md bg-muted" />
        <li className="h-8 animate-pulse rounded-md bg-muted" />
        <li className="h-8 animate-pulse rounded-md bg-muted" />
      </ul>
    ),
  };

  const analystChatSection: WorkspaceSection = {
    id: "analyst-chat",
    title: "Analyst Chat",
    description: "Host scoped multi-turn Q&A with source-grounded answers from ingested reviews.",
    status: canAnalyzeSelectedProduct ? "ready" : "loading",
    placeholder: canAnalyzeSelectedProduct ? (
      <AnalystChatPanel
        messages={chatMessages}
        onSubmitQuestion={appendQuestionToChat}
        disabled={false}
        isResponding={isChatResponding}
        onCancelResponse={cancelActiveResponse}
      />
    ) : (
      <div className="space-y-3">
        <div className="h-24 animate-pulse rounded-md bg-muted" />
        <div className="h-24 animate-pulse rounded-md bg-muted" />
        <div className="h-10 animate-pulse rounded-md bg-muted" />
      </div>
    ),
  };

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <WorkspaceSectionCard
        section={{
          id: "product-selector",
          title: "Products",
          description: "Each source URL is tracked as a separate product. Select one to analyze in isolation.",
          status: isProductsLoading ? "loading" : "ready",
          placeholder: isProductsLoading ? (
            <div className="grid gap-3">
              <div className="h-24 animate-pulse rounded-md bg-muted" />
              <div className="h-24 animate-pulse rounded-md bg-muted" />
            </div>
          ) : products.length > 0 ? (
            <div className="grid gap-3">
              {products.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onAnalyze={setSelectedProductId}
                  className={
                    product.id === selectedProductId
                      ? "border-primary ring-1 ring-primary/30"
                      : ""
                  }
                />
              ))}
            </div>
          ) : (
            <p className="rounded-md border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
              No products yet. Run URL ingestion and each unique URL will be stored as its own product.
            </p>
          ),
        }}
      />
      <WorkspaceSectionCard
        section={{
          id: "ingestion-panel",
          title: "Ingestion Panel",
          description: "Submit a URL or upload CSV reviews for the currently selected product.",
          status: "ready",
          placeholder: (
            <IngestionPanel
              onProductSelected={setSelectedProductId}
              onIngestionSuccess={(result) => {
                setLatestIngestion(result);
                void loadProducts();
              }}
            />
          ),
        }}
      />
      <WorkspaceSectionCard key={summarySection.id} section={summarySection} />
      <WorkspaceSectionCard key={suggestedQuestionsSection.id} section={suggestedQuestionsSection} />
      <WorkspaceSectionCard key={analystChatSection.id} section={analystChatSection} />
    </div>
  );
}
