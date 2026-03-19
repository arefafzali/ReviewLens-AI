"use client";

import React, { useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";

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

type DraftIngestionPayload =
  | {
      mode: "url";
      targetUrl: string;
    }
  | {
      mode: "csv";
      filename: string;
      sizeBytes: number;
    };

const MAX_CSV_BYTES = 5 * 1024 * 1024;

function validateCapterraUrl(rawValue: string): string | null {
  const trimmed = rawValue.trim();
  if (!trimmed) {
    return "Enter a review page URL.";
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

//   if (!parsed.hostname.toLowerCase().includes("capterra")) {
//     return "Only URLs are supported in this workflow.";
//   }

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

export function IngestionPanel(): ReactNode {
  const [mode, setMode] = useState<SubmissionMode>("url");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<FormNotice | null>(null);
  const [urlForm, setUrlForm] = useState<URLFormState>({ targetUrl: "", error: null });
  const [csvForm, setCsvForm] = useState<CSVFormState>({ file: null, error: null });

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
  }

  async function submitUrl(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const nextError = validateCapterraUrl(urlForm.targetUrl);
    setUrlForm((prev) => ({ ...prev, error: nextError }));
    setNotice(null);

    if (nextError) {
      return;
    }

    const draft: DraftIngestionPayload = {
      mode: "url",
      targetUrl: urlForm.targetUrl.trim(),
    };

    setIsSubmitting(true);
    await Promise.resolve();
    setIsSubmitting(false);
    setNotice({
      tone: "success",
      message: `URL payload ready for backend integration: ${draft.targetUrl}`,
    });
  }

  async function submitCsv(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const nextError = validateCsvFile(csvForm.file);
    setCsvForm((prev) => ({ ...prev, error: nextError }));
    setNotice(null);

    if (nextError || !csvForm.file) {
      return;
    }

    const draft: DraftIngestionPayload = {
      mode: "csv",
      filename: csvForm.file.name,
      sizeBytes: csvForm.file.size,
    };

    setIsSubmitting(true);
    await Promise.resolve();
    setIsSubmitting(false);
    setNotice({
      tone: "success",
      message: `CSV payload ready for backend integration: ${draft.filename} (${draft.sizeBytes} bytes)`,
    });
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
        >
          Ingest from URL
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "csv"}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
          onClick={() => switchMode("csv")}
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
              const value = event.target.value;
              setUrlForm({ targetUrl: value, error: null });
              setNotice(null);
            }}
            aria-invalid={urlForm.error ? "true" : "false"}
            aria-describedby="ingestion-url-help ingestion-url-error"
          />
          <p id="ingestion-url-help" className="text-xs text-muted-foreground">
            Paste the public URL for the product review page.
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
          >
            {isSubmitting ? "Preparing..." : "Prepare URL Ingestion"}
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
          >
            {isSubmitting ? "Preparing..." : "Prepare CSV Ingestion"}
          </button>
        </form>
      )}

      {notice ? (
        <p
          className={
            notice.tone === "error"
              ? "rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs font-medium text-red-700"
              : "rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700"
          }
          role="status"
        >
          {notice.message}
        </p>
      ) : null}
    </div>
  );
}
