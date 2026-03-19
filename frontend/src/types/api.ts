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

export type IngestionSourceType = "scrape" | "csv_upload";
export type IngestionRunStatus = "running" | "success" | "partial" | "failed";
export type IngestionOutcomeCode =
  | "ok"
  | "low_data"
  | "blocked"
  | "parse_failed"
  | "unsupported_source"
  | "invalid_url"
  | "empty_csv"
  | "malformed_csv";

export type URLIngestionPayload = {
  workspace_id: string;
  product_id: string;
  target_url: string;
  reload?: boolean;
};

export type CSVIngestionPayload = {
  workspace_id: string;
  product_id: string;
  csv_filename?: string | null;
  csv_content: string;
};

export type EnsureContextPayload = {
  workspace_id: string;
  product_id: string;
  platform?: string;
  product_name?: string;
  source_url?: string;
};

export type EnsureContextResponse = {
  workspace_id: string;
  product_id: string;
  created_workspace: boolean;
  created_product: boolean;
};

export type IngestionKeywordCount = {
  keyword: string;
  count: number;
};

export type IngestionTimeBucket = {
  date: string;
  count: number;
};

export type IngestionDateRange = {
  start: string | null;
  end: string | null;
};

export type IngestionAnalyticsSummary = {
  total_reviews?: number;
  rated_reviews?: number;
  average_rating?: number | null;
  rating_histogram?: Record<string, number>;
  review_count_over_time?: IngestionTimeBucket[];
  date_range?: IngestionDateRange;
  top_keywords?: IngestionKeywordCount[];
};

export type IngestionAttemptResponse = {
  ingestion_run_id: string;
  source_type: IngestionSourceType;
  status: IngestionRunStatus;
  outcome_code: IngestionOutcomeCode;
  captured_reviews: number;
  message: string;
  warnings: string[];
  diagnostics: Record<string, unknown>;
  summary_snapshot: IngestionAnalyticsSummary;
  started_at: string | null;
  completed_at: string | null;
};

export type FastApiValidationIssue = {
  loc: Array<string | number>;
  msg: string;
  type: string;
};

export type FastApiErrorResponse = {
  detail: string | FastApiValidationIssue[];
};
