import type {
  ApiErrorResponse,
  CSVIngestionPayload,
  EnsureContextPayload,
  EnsureContextResponse,
  ChatHistoryResponse,
  FastApiErrorResponse,
  HealthResponse,
  IngestionAttemptResponse,
  ProductDetailResponse,
  ProductListItem,
  URLIngestionPayload,
} from "@/types/api";

export type ApiClientConfig = {
  baseUrl?: string;
  timeoutMs?: number;
};

export class ApiClientError extends Error {
  readonly status: number;
  readonly payload?: ApiErrorResponse;
  readonly rawPayload?: unknown;

  constructor(message: string, status: number, payload?: ApiErrorResponse, rawPayload?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.payload = payload;
    this.rawPayload = rawPayload;
  }
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly ingestionTimeoutMs: number;

  constructor(config: ApiClientConfig = {}) {
    this.baseUrl = config.baseUrl ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    this.timeoutMs = config.timeoutMs ?? 10_000;
    this.ingestionTimeoutMs = this.parseIngestionTimeoutMs(process.env.NEXT_PUBLIC_INGESTION_TIMEOUT_MS);
  }

  async getHealthLive(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health/live", { method: "GET" });
  }

  async getHealthReady(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health/ready", { method: "GET" });
  }

  async postUrlIngestion(payload: URLIngestionPayload): Promise<IngestionAttemptResponse> {
    return this.request<IngestionAttemptResponse>("/ingestion/url", {
      method: "POST",
      body: JSON.stringify(payload),
    }, this.ingestionTimeoutMs);
  }

  async postCsvIngestion(payload: CSVIngestionPayload): Promise<IngestionAttemptResponse> {
    return this.request<IngestionAttemptResponse>("/ingestion/csv", {
      method: "POST",
      body: JSON.stringify(payload),
    }, this.ingestionTimeoutMs);
  }

  async postEnsureContext(payload: EnsureContextPayload): Promise<EnsureContextResponse> {
    return this.request<EnsureContextResponse>("/context/ensure", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getChatHistory(
    workspaceId: string,
    productId: string,
    chatSessionId?: string,
    maxTurns: number = 6,
  ): Promise<ChatHistoryResponse> {
    const params = new URLSearchParams({
      workspace_id: workspaceId,
      product_id: productId,
      max_turns: String(maxTurns),
    });
    if (chatSessionId) {
      params.set("chat_session_id", chatSessionId);
    }
    return this.request<ChatHistoryResponse>(`/chat/history?${params.toString()}`, { method: "GET" });
  }

  async getProducts(workspaceId: string): Promise<ProductListItem[]> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    return this.request<ProductListItem[]>(`/products?${params.toString()}`, { method: "GET" });
  }

  async getProduct(workspaceId: string, productId: string): Promise<ProductDetailResponse> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    return this.request<ProductDetailResponse>(`/products/${productId}?${params.toString()}`, { method: "GET" });
  }

  async deleteProduct(workspaceId: string, productId: string): Promise<void> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    await this.request<unknown>(`/products/${productId}?${params.toString()}`, { method: "DELETE" });
  }

  private async request<T>(path: string, init: RequestInit, timeoutMs: number = this.timeoutMs): Promise<T> {
    const controller = new AbortController();
    const timeout = timeoutMs > 0 ? setTimeout(() => controller.abort(), timeoutMs) : null;

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        signal: controller.signal,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(init.headers ?? {}),
        },
      });

      if (!response.ok) {
        let payload: ApiErrorResponse | undefined;
        let rawPayload: unknown;
        try {
          rawPayload = (await response.json()) as ApiErrorResponse | FastApiErrorResponse;

          const maybePayload = rawPayload as ApiErrorResponse;
          if (maybePayload && typeof maybePayload === "object" && "error" in maybePayload) {
            payload = maybePayload;
          }
        } catch {
          payload = undefined;
          rawPayload = undefined;
        }

        throw new ApiClientError(
          payload?.error.message ?? `Request failed with status ${response.status}`,
          response.status,
          payload,
          rawPayload,
        );
      }

      return (await response.json()) as T;
    } finally {
      if (timeout !== null) {
        clearTimeout(timeout);
      }
    }
  }

  private parseIngestionTimeoutMs(raw: string | undefined): number {
    // Default to no client timeout for ingestion, since extraction can take minutes.
    if (!raw || raw.trim() === "") {
      return 0;
    }

    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed < 0) {
      return 0;
    }

    return Math.floor(parsed);
  }
}

export const apiClient = new ApiClient();
