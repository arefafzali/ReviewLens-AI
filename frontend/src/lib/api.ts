import type { ApiErrorResponse, HealthResponse } from "@/types/api";

export type ApiClientConfig = {
  baseUrl?: string;
  timeoutMs?: number;
};

export class ApiClientError extends Error {
  readonly status: number;
  readonly payload?: ApiErrorResponse;

  constructor(message: string, status: number, payload?: ApiErrorResponse) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.payload = payload;
  }
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  constructor(config: ApiClientConfig = {}) {
    this.baseUrl = config.baseUrl ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    this.timeoutMs = config.timeoutMs ?? 10_000;
  }

  async getHealthLive(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health/live", { method: "GET" });
  }

  async getHealthReady(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health/ready", { method: "GET" });
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...(init.headers ?? {}),
        },
      });

      if (!response.ok) {
        let payload: ApiErrorResponse | undefined;
        try {
          payload = (await response.json()) as ApiErrorResponse;
        } catch {
          payload = undefined;
        }

        throw new ApiClientError(
          payload?.error.message ?? `Request failed with status ${response.status}`,
          response.status,
          payload,
        );
      }

      return (await response.json()) as T;
    } finally {
      clearTimeout(timeout);
    }
  }
}

export const apiClient = new ApiClient();
