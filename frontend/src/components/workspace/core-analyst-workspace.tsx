"use client";

import React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

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

type DashboardNotice = {
  tone: "success" | "error";
  message: string;
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

function buildOptimisticProductFromIngestion(
  context: {
    workspaceId: string;
    productId: string;
    sourceUrl?: string;
    productName?: string;
    platform: string;
  },
  result: IngestionAttemptResponse,
  current?: ProductListItem,
): ProductListItem {
  const nowIso = new Date().toISOString();
  const fallbackName = context.productName?.trim() || current?.name || "Analyst Product";
  const totalReviews = result.summary_snapshot.total_reviews ?? result.captured_reviews;
  const avgRating =
    typeof result.summary_snapshot.average_rating === "number"
      ? result.summary_snapshot.average_rating
      : (current?.average_rating ?? null);

  return {
    id: context.productId,
    workspace_id: context.workspaceId,
    platform: context.platform || current?.platform || "generic",
    name: fallbackName,
    source_url: context.sourceUrl || current?.source_url || "https://example.com/reviews",
    total_reviews: Math.max(0, totalReviews),
    average_rating: avgRating,
    chat_session_count: current?.chat_session_count ?? 0,
    latest_ingestion: {
      ingestion_run_id: result.ingestion_run_id,
      status: result.status,
      outcome_code: result.outcome_code,
      completed_at: result.completed_at,
    },
    updated_at: nowIso,
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
  const [dashboardNotice, setDashboardNotice] = useState<DashboardNotice | null>(null);
  const [pendingDeleteProductId, setPendingDeleteProductId] = useState<string | null>(null);
  const [isRecapturing, setIsRecapturing] = useState(false);

  const activeStreamControllerRef = useRef<AbortController | null>(null);
  const streamEpochRef = useRef(0);
  const selectedProductIdRef = useRef(selectedProductId);
  const selectedProduct = products.find((item) => item.id === selectedProductId) ?? null;
  const canAnalyzeSelectedProduct = Boolean(latestIngestion) || (selectedProduct?.total_reviews ?? 0) > 0 || chatMessages.length > 0;

  const suggestedQuestions = latestIngestion?.summary_snapshot?.suggested_questions ?? [];
  const hasConversationStarted = chatMessages.length > 0;
  const hasLoadedProduct = Boolean(selectedProduct);

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
      setDashboardNotice({ tone: "error", message: "Unable to refresh products right now." });
    } finally {
      setIsProductsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    selectedProductIdRef.current = selectedProductId;
  }, [selectedProductId]);

  useEffect(() => {
    if (!selectedProductId) {
      return;
    }
    setActiveProductId(workspaceId, selectedProductId);
  }, [workspaceId, selectedProductId]);

  useEffect(() => {
    if (!dashboardNotice || dashboardNotice.tone === "error") {
      return;
    }

    const timer = window.setTimeout(() => {
      setDashboardNotice(null);
    }, 2800);

    return () => {
      window.clearTimeout(timer);
    };
  }, [dashboardNotice]);

  useEffect(() => {
    let canceled = false;
    const storedSessionId = getStoredChatSessionId(workspaceId, selectedProductId) ?? undefined;

    streamEpochRef.current += 1;
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
    const streamEpoch = ++streamEpochRef.current;
    const streamProductId = selectedProductId;

    function isActiveStream(): boolean {
      return streamEpochRef.current === streamEpoch && streamProductId === selectedProductIdRef.current;
    }

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
          if (!isActiveStream()) {
            return;
          }
          setChatSessionId(meta.chat_session_id);
          setStoredChatSessionId(workspaceId, selectedProductId, meta.chat_session_id);
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
          setStoredChatSessionId(workspaceId, selectedProductId, payload.chat_session_id);
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

  function applyIngestionSuccess(
    result: IngestionAttemptResponse,
    context: {
      workspaceId: string;
      productId: string;
      sourceUrl?: string;
      productName?: string;
      platform: string;
    },
  ): void {
    setLatestIngestion(result);
    setProducts((previous) => {
      const existing = previous.find((item) => item.id === context.productId);
      const optimistic = buildOptimisticProductFromIngestion(context, result, existing);
      const withoutCurrent = previous.filter((item) => item.id !== context.productId);
      return [optimistic, ...withoutCurrent];
    });
    setSelectedProductId(context.productId);
    setDashboardNotice({ tone: "success", message: "Ingestion complete. Product list updated." });

    void apiClient
      .getProduct(workspaceId, context.productId)
      .then((detail) => {
        setProducts((previous) => previous.map((item) => {
          if (item.id !== context.productId) {
            return item;
          }

          return {
            ...item,
            platform: detail.platform,
            name: detail.name,
            source_url: detail.source_url,
            total_reviews: detail.total_reviews,
            average_rating: detail.average_rating,
            chat_session_count: detail.chat_session_count,
            latest_ingestion: detail.latest_ingestion,
            updated_at: detail.updated_at,
          };
        }));
      })
      .catch(() => {
        void apiClient
          .getProducts(workspaceId)
          .then((items) => {
            setProducts(items);
          })
          .catch(() => {
            setDashboardNotice({
              tone: "error",
              message: "Product update confirmation is delayed. Showing optimistic data.",
            });
          });
      });
  }

  async function handleRecaptureCurrentProduct(): Promise<void> {
    if (!selectedProduct || isRecapturing) {
      return;
    }

    setIsRecapturing(true);
    setDashboardNotice({ tone: "success", message: "Recapturing latest data..." });

    try {
      const result = await apiClient.postUrlIngestion({
        workspace_id: workspaceId,
        product_id: selectedProduct.id,
        target_url: selectedProduct.source_url,
        reload: true,
      });

      applyIngestionSuccess(result, {
        workspaceId,
        productId: selectedProduct.id,
        sourceUrl: selectedProduct.source_url,
        productName: selectedProduct.name,
        platform: selectedProduct.platform,
      });
    } catch {
      setDashboardNotice({
        tone: "error",
        message: "Recapture failed. Please try again.",
      });
    } finally {
      setIsRecapturing(false);
    }
  }

  async function handleDeleteProduct(productId: string): Promise<void> {
    if (pendingDeleteProductId) {
      return;
    }

    const snapshot = products;
    const removed = snapshot.find((item) => item.id === productId);
    if (!removed) {
      return;
    }

    const remaining = snapshot.filter((item) => item.id !== productId);
    const nextSelectedProductId =
      selectedProductId === productId
        ? (remaining[0]?.id ?? "")
        : selectedProductId;

    setPendingDeleteProductId(productId);
    setProducts(remaining);
    setSelectedProductId(nextSelectedProductId);
    setDashboardNotice({ tone: "success", message: `Removed ${removed.name}...` });

    try {
      await apiClient.deleteProduct(workspaceId, productId);
      setDashboardNotice({ tone: "success", message: `Deleted ${removed.name}.` });
    } catch {
      setProducts(snapshot);
      setSelectedProductId(selectedProductId);
      setDashboardNotice({ tone: "error", message: `Could not delete ${removed.name}. Restored product list.` });
    } finally {
      setPendingDeleteProductId(null);
    }
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
    status: canAnalyzeSelectedProduct ? "ready" : "loading",
    placeholder: canAnalyzeSelectedProduct ? (
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

  const productSection: WorkspaceSection = {
    id: "product-selector",
    title: "Products",
    description: "Select a product to load its isolated summary and chat context.",
    status: isProductsLoading ? "loading" : "ready",
    placeholder: isProductsLoading ? (
      <div className="grid gap-3">
        <div className="h-24 animate-pulse rounded-md bg-muted" />
        <div className="h-24 animate-pulse rounded-md bg-muted" />
      </div>
    ) : products.length > 0 ? (
      <div className="space-y-3">
        {dashboardNotice ? (
          <div
            role={dashboardNotice.tone === "error" ? "alert" : "status"}
            className={
              dashboardNotice.tone === "error"
                ? "flex items-center justify-between gap-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700"
                : "flex items-center justify-between gap-2 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs text-emerald-700"
            }
          >
            <span>{dashboardNotice.message}</span>
            {dashboardNotice.tone === "error" ? (
              <button
                type="button"
                onClick={() => setDashboardNotice(null)}
                className="rounded border border-current/30 px-1.5 py-0.5 text-[11px] font-medium"
              >
                Dismiss
              </button>
            ) : null}
          </div>
        ) : null}
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => {
              setSelectedProductId("");
              setLatestIngestion(null);
              setChatMessages([]);
              setChatSessionId(null);
            }}
            className="rounded-md border border-border bg-background px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted"
          >
            New Product
          </button>
        </div>

        <ul className="space-y-1" aria-label="Products list">
          {products.map((product) => {
            const isSelected = product.id === selectedProductId;
            return (
              <li key={product.id}>
                <div
                  className={[
                    "rounded-lg border px-3 py-2",
                    isSelected
                      ? "border-primary bg-primary/5"
                      : "border-border bg-background hover:bg-muted/30",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{product.name}</p>
                      <p className="mt-0.5 text-[11px] text-muted-foreground">
                        {product.total_reviews} reviews
                      </p>
                    </div>

                    <button
                      type="button"
                      aria-label={`Delete product ${product.name}`}
                      disabled={pendingDeleteProductId === product.id}
                      onClick={() => {
                        void handleDeleteProduct(product.id);
                      }}
                      className="rounded-md border border-border bg-background px-2 py-1 text-[11px] font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {pendingDeleteProductId === product.id ? "Deleting..." : "Delete"}
                    </button>
                  </div>

                  <div className="mt-2 flex items-center justify-end">
                    <button
                      type="button"
                      onClick={() => setSelectedProductId(product.id)}
                      className="rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:opacity-95"
                    >
                      Analyze
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    ) : (
      <p className="rounded-md border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
        No products yet. Run URL ingestion and each unique URL will be stored as its own product.
      </p>
    ),
  };

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
      <aside
        className="w-full lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:w-[19.5rem] lg:shrink-0 lg:overflow-y-auto"
        aria-label="Products sidebar"
      >
        <WorkspaceSectionCard section={productSection} />
      </aside>

      <main className="min-w-0 flex-1 space-y-4">
      <WorkspaceSectionCard
        section={{
          id: "ingestion-panel",
          title: hasLoadedProduct ? "Product Source" : "Ingestion Panel",
          description: hasLoadedProduct
            ? "Current loaded product source and recapture controls."
            : "Submit a URL or upload CSV reviews to start a new product context.",
          status: "ready",
          placeholder: hasLoadedProduct ? (
            <div className="space-y-3 rounded-md border border-border bg-muted/20 p-3">
              <div>
                <p className="text-xs text-muted-foreground">Loaded source URL</p>
                <p className="mt-1 break-all text-sm font-medium text-foreground">{selectedProduct?.source_url}</p>
              </div>

              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground">
                  Use recapture to refresh this product with the latest source data.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    void handleRecaptureCurrentProduct();
                  }}
                  disabled={isRecapturing}
                  className="rounded-md bg-primary px-3 py-2 text-xs font-medium text-primary-foreground hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isRecapturing ? "Recapturing..." : "Recapture Data"}
                </button>
              </div>
            </div>
          ) : (
            <IngestionPanel
              onProductSelected={setSelectedProductId}
              onIngestionSuccess={(result, context) => {
                applyIngestionSuccess(result, context);
              }}
            />
          ),
        }}
      />
      <WorkspaceSectionCard key={summarySection.id} section={summarySection} />
      <WorkspaceSectionCard key={analystChatSection.id} section={analystChatSection} />
      </main>
    </div>
  );
}
