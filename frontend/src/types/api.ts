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
  suggested_questions?: string[];
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

export type ChatClassification = "answer" | "out_of_scope" | "insufficient_evidence";

export type ChatCitationItem = {
  evidence_id: string;
  review_id: string;
  title?: string | null;
  snippet: string;
  author_name?: string | null;
  reviewed_at?: string | null;
  rating?: number | null;
  rank: number;
};

export type ChatStreamRequestPayload = {
  workspace_id: string;
  product_id: string;
  question: string;
  chat_session_id?: string;
};

export type ChatStreamMetaEvent = {
  chat_session_id: string;
  provider: string;
  history_message_count: number;
};

export type ChatStreamCitationsEvent = {
  items: ChatCitationItem[];
};

export type ChatStreamTokenEvent = {
  text: string;
};

export type ChatStreamDoneEvent = {
  classification: ChatClassification;
  chat_session_id: string;
  citations: ChatCitationItem[];
  answer: string;
};

export type ChatStreamErrorEvent = {
  code: string;
  message: string;
};

export type PersistedChatMessage = {
  message_index: number;
  role: "user" | "assistant";
  content: string;
  is_refusal: boolean;
  metadata: Record<string, unknown>;
};

export type ChatHistoryResponse = {
  chat_session_id: string;
  messages: PersistedChatMessage[];
};
