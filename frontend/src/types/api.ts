export type ApiErrorDetail = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

export type ApiErrorResponse = {
  error: ApiErrorDetail;
};

export type HealthStatus = "live" | "ready";

export type HealthResponse = {
  status: HealthStatus;
};
