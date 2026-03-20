"use client";

import React, { useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import { ApiClientError, apiClient } from "@/lib/api";
import {
  getOrCreateProductContextForCsv,
  getOrCreateProductContextForUrl,
} from "@/lib/workspace-context";
import type { FastApiErrorResponse, FastApiValidationIssue, IngestionAttemptResponse } from "@/types/api";

type SubmissionMode = "url" | "csv";

type FormNotice = {
  tone: "error" | "success";
  message: string;
};

type URLFormState = {
  targetUrl: string;
  error: string | null;
};

type CSVFormState = {
  file: File | null;
  error: string | null;
};

const MAX_CSV_BYTES = 5 * 1024 * 1024;

type IngestionPanelProps = {
  onIngestionSuccess?: (
    result: IngestionAttemptResponse,
    context: {
      workspaceId: string;
      productId: string;
      sourceUrl?: string;
      productName?: string;
      platform: string;
    },
  ) => void;
  onProductSelected?: (productId: string) => void;
};

async function ensureBackendContext(
  workspaceId: string,
  productId: string,
  sourceUrl: string | undefined,
  productName?: string,
  platform: "generic" | "csv" = "generic",
): Promise<void> {
  await apiClient.postEnsureContext({
    workspace_id: workspaceId,
    product_id: productId,
    platform,
    product_name: productName ?? "Analyst Product",
    source_url: sourceUrl,
  });
}

function validatePublicReviewUrl(rawValue: string): string | null {
  const trimmed = rawValue.trim();
  if (!trimmed) {
    return "Enter a public review page URL.";
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return "Enter a valid URL, including https://.";
  }

  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    return "Only HTTP or HTTPS URLs are supported.";
  }

  return null;
}

function validateCsvFile(file: File | null): string | null {
  if (!file) {
    return "Select a CSV file to continue.";
  }

  const lowerName = file.name.toLowerCase();
  if (!lowerName.endsWith(".csv")) {
    return "Upload a .csv file.";
  }

  if (file.size <= 0) {
    return "CSV file is empty.";
  }

  if (file.size > MAX_CSV_BYTES) {
    return "CSV file is too large. Maximum size is 5 MB.";
  }

  return null;
}

async function readFileAsText(file: File): Promise<string> {
  if (typeof file.text === "function") {
    return file.text();
  }

  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      resolve(typeof reader.result === "string" ? reader.result : "");
    };
    reader.onerror = () => {
      reject(new Error("Unable to read CSV file."));
    };
    reader.readAsText(file);
  });
}

function parseFastApiValidationIssues(issues: FastApiValidationIssue[]): string {
  const first = issues[0];
  const msg = first?.msg ?? "Request validation failed.";
  return `Some input values are invalid: ${msg}`;
}

function extractBackendErrorMessage(error: unknown): string {
  if (error instanceof Error && error.name === "AbortError") {
    return "Ingestion is taking longer than expected. Please wait and retry in a moment.";
  }

  if (error instanceof ApiClientError) {
    if (error.payload?.error?.message) {
      return error.payload.error.message;
    }

    const rawPayload = error.rawPayload as FastApiErrorResponse | undefined;
    if (rawPayload?.detail) {
      if (typeof rawPayload.detail === "string") {
        return rawPayload.detail;
      }

      if (Array.isArray(rawPayload.detail) && rawPayload.detail.length > 0) {
        return parseFastApiValidationIssues(rawPayload.detail);
      }
    }

    return "The ingestion request failed. Please try again.";
  }

  return "Unable to submit ingestion request. Please try again.";
}

function shouldSuggestCsvFallback(result: IngestionAttemptResponse | null): boolean {
  if (!result) {
    return false;
  }

  return result.outcome_code === "blocked" || result.outcome_code === "low_data" || result.outcome_code === "parse_failed";
}

function renderResultTone(result: IngestionAttemptResponse): "error" | "success" {
  if (result.status === "failed") {
    return "error";
  }
  return "success";
}

export function IngestionPanel({ onIngestionSuccess, onProductSelected }: IngestionPanelProps): ReactNode {
  const [mode, setMode] = useState<SubmissionMode>("url");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [progressText, setProgressText] = useState<string | null>(null);
  const [notice, setNotice] = useState<FormNotice | null>(null);
  const [urlForm, setUrlForm] = useState<URLFormState>({ targetUrl: "", error: null });
  const [csvForm, setCsvForm] = useState<CSVFormState>({ file: null, error: null });
  const [lastResult, setLastResult] = useState<IngestionAttemptResponse | null>(null);

  const csvHelper = useMemo(() => {
    if (!csvForm.file) {
      return "Accepted format: .csv up to 5 MB.";
    }
    const sizeKb = Math.max(1, Math.round(csvForm.file.size / 1024));
    return `Selected: ${csvForm.file.name} (${sizeKb} KB)`;
  }, [csvForm.file]);

  function switchMode(nextMode: SubmissionMode): void {
    setMode(nextMode);
    setNotice(null);
    setProgressText(null);
  }

  function commitSuccessResult(
    result: IngestionAttemptResponse,
    context: {
      workspaceId: string;
      productId: string;
      sourceUrl?: string;
      productName?: string;
      platform: string;
    },
  ): void {
    setLastResult(result);
    setNotice({ tone: renderResultTone(result), message: result.message });
    onIngestionSuccess?.(result, context);
  }

  async function submitUrl(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const nextError = validatePublicReviewUrl(urlForm.targetUrl);
    setUrlForm((prev) => ({ ...prev, error: nextError }));
    setNotice(null);

    if (nextError) {
      return;
    }

    setIsSubmitting(true);
    setProgressText("Submitting URL ingestion request...");

    try {
      const context = getOrCreateProductContextForUrl(urlForm.targetUrl.trim());
      await ensureBackendContext(context.workspaceId, context.productId, context.sourceUrl, context.productName, "generic");
      const result = await apiClient.postUrlIngestion({
        workspace_id: context.workspaceId,
        product_id: context.productId,
        target_url: context.sourceUrl,
        reload: false,
      });

      onProductSelected?.(context.productId);
      commitSuccessResult(result, {
        workspaceId: context.workspaceId,
        productId: context.productId,
        sourceUrl: context.sourceUrl,
        productName: context.productName,
        platform: "generic",
      });
    } catch (error) {
      setNotice({ tone: "error", message: extractBackendErrorMessage(error) });
    } finally {
      setProgressText(null);
      setIsSubmitting(false);
    }
  }

  async function submitCsv(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const nextError = validateCsvFile(csvForm.file);
    setCsvForm((prev) => ({ ...prev, error: nextError }));
    setNotice(null);

    if (nextError || !csvForm.file) {
      return;
    }

    setIsSubmitting(true);

    try {
      setProgressText("Reading selected CSV file...");
      const csvContent = await readFileAsText(csvForm.file);
      const context = await getOrCreateProductContextForCsv(csvForm.file.name, csvContent);

      setProgressText("Uploading CSV for ingestion and parsing...");
      await ensureBackendContext(context.workspaceId, context.productId, context.sourceUrl, context.productName, "csv");
      const result = await apiClient.postCsvIngestion({
        workspace_id: context.workspaceId,
        product_id: context.productId,
        source_ref: context.sourceUrl,
        csv_content: csvContent,
      });

      onProductSelected?.(context.productId);
      commitSuccessResult(result, {
        workspaceId: context.workspaceId,
        productId: context.productId,
        sourceUrl: context.sourceUrl,
        productName: context.productName,
        platform: "csv",
      });
    } catch (error) {
      setNotice({ tone: "error", message: extractBackendErrorMessage(error) });
    } finally {
      setProgressText(null);
      setIsSubmitting(false);
    }
  }

  const inputBaseClass =
    "w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <div className="space-y-4">
      <div className="grid gap-2 sm:grid-cols-2" role="tablist" aria-label="Ingestion source">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "url"}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
          onClick={() => switchMode("url")}
          disabled={isSubmitting}
          suppressHydrationWarning
        >
          Ingest from URL
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "csv"}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
          onClick={() => switchMode("csv")}
          disabled={isSubmitting}
          suppressHydrationWarning
        >
          Upload CSV
        </button>
      </div>

      {mode === "url" ? (
        <form key="url-form" className="space-y-3" onSubmit={submitUrl} noValidate>
          <label htmlFor="ingestion-url" className="block text-sm font-medium text-foreground">
            Review page URL
          </label>
          <input
            id="ingestion-url"
            name="ingestion-url"
            type="url"
            inputMode="url"
            autoComplete="off"
            className={inputBaseClass}
            placeholder="https://example.com/reviews/"
            value={urlForm.targetUrl}
            onChange={(event) => {
              setUrlForm({ targetUrl: event.target.value, error: null });
              setNotice(null);
            }}
            aria-invalid={urlForm.error ? "true" : "false"}
            aria-describedby="ingestion-url-help ingestion-url-error"
            suppressHydrationWarning
          />
          <p id="ingestion-url-help" className="text-xs text-muted-foreground">
            Paste the public URL for a product review page.
          </p>
          {urlForm.error ? (
            <p id="ingestion-url-error" className="text-xs font-medium text-red-700">
              {urlForm.error}
            </p>
          ) : null}
          <button
            type="submit"
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSubmitting}
            suppressHydrationWarning
          >
            {isSubmitting ? "Submitting..." : "Run URL Ingestion"}
          </button>
        </form>
      ) : (
        <form key="csv-form" className="space-y-3" onSubmit={submitCsv} noValidate>
          <label htmlFor="ingestion-csv" className="block text-sm font-medium text-foreground">
            Review CSV file
          </label>
          <input
            id="ingestion-csv"
            name="ingestion-csv"
            type="file"
            accept=".csv,text/csv"
            className={inputBaseClass}
            onChange={(event) => {
              const selected = event.target.files && event.target.files[0] ? event.target.files[0] : null;
              setCsvForm({ file: selected, error: null });
              setNotice(null);
            }}
            aria-invalid={csvForm.error ? "true" : "false"}
            aria-describedby="ingestion-csv-help ingestion-csv-error"
            suppressHydrationWarning
          />
          <p id="ingestion-csv-help" className="text-xs text-muted-foreground">
            {csvHelper}
          </p>
          {csvForm.error ? (
            <p id="ingestion-csv-error" className="text-xs font-medium text-red-700">
              {csvForm.error}
            </p>
          ) : null}
          <button
            type="submit"
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSubmitting}
            suppressHydrationWarning
          >
            {isSubmitting ? "Uploading..." : "Run CSV Ingestion"}
          </button>
          <p className="text-xs text-muted-foreground">
            Use this fallback when URL ingestion is blocked or captures too little review data.
          </p>
        </form>
      )}

      {progressText ? <p className="text-xs text-muted-foreground">{progressText}</p> : null}

      {shouldSuggestCsvFallback(lastResult) && mode === "url" ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          <p className="font-medium">URL ingestion may be incomplete.</p>
          <p className="mt-1">Try CSV fallback to continue analysis with complete review data.</p>
          <button
            type="button"
            onClick={() => switchMode("csv")}
            className="mt-2 rounded-md border border-amber-400 bg-amber-100 px-2 py-1 font-medium hover:bg-amber-200"
            suppressHydrationWarning
          >
            Switch to CSV fallback
          </button>
        </div>
      ) : null}

      {lastResult ? (
        <dl className="grid gap-2 rounded-md border border-border bg-muted/50 p-3 text-xs sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Run ID</dt>
            <dd className="font-medium text-foreground">{lastResult.ingestion_run_id}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Status</dt>
            <dd className="font-medium text-foreground">{lastResult.status}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Outcome</dt>
            <dd className="font-medium text-foreground">{lastResult.outcome_code}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Captured Reviews</dt>
            <dd className="font-medium text-foreground">{lastResult.captured_reviews}</dd>
          </div>
        </dl>
      ) : null}

      {notice ? (
        <p
          className={
            notice.tone === "error"
              ? "rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs font-medium text-red-700"
              : "rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700"
          }
          role={notice.tone === "error" ? "alert" : "status"}
        >
          {notice.message}
        </p>
      ) : null}
    </div>
  );
}
