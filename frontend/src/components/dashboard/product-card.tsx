"use client";

import React from "react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { ProductListItem } from "@/types/api";

type ProductCardProps = {
  product: ProductListItem;
  onAnalyze: (productId: string) => void;
  deleteAction?: ReactNode;
  className?: string;
};

function formatPlatformLabel(platform: string): string {
  const trimmed = platform.trim();
  if (!trimmed) {
    return "Unknown";
  }
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
}

function formatAverageRating(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "N/A";
  }
  return `${value.toFixed(2)} / 5`;
}

function formatCaptureTime(raw: string | null | undefined): string {
  if (!raw) {
    return "Capture pending";
  }

  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return "Capture pending";
  }

  return parsed.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sourceHostLabel(sourceUrl: string): string {
  try {
    const host = new URL(sourceUrl).hostname;
    return host || "unknown-source";
  } catch {
    return "unknown-source";
  }
}

export function ProductCard({ product, onAnalyze, deleteAction, className }: ProductCardProps): ReactNode {
  const sourceBadge = `${formatPlatformLabel(product.platform)} - ${sourceHostLabel(product.source_url)}`;
  const captureTime = formatCaptureTime(product.latest_ingestion?.completed_at);

  return (
    <article
      className={[
        "rounded-xl border border-border bg-card p-4 shadow-sm",
        className ?? "",
      ].join(" ").trim()}
      aria-label={`Product card ${product.name}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-foreground">{product.name}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{sourceBadge}</p>
        </div>
        {deleteAction ? <div className="shrink-0">{deleteAction}</div> : null}
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-md border border-border/70 bg-muted/20 p-2">
          <dt className="text-xs text-muted-foreground">Reviews</dt>
          <dd className="mt-1 font-medium text-foreground">{Math.max(0, product.total_reviews)}</dd>
        </div>
        <div className="rounded-md border border-border/70 bg-muted/20 p-2">
          <dt className="text-xs text-muted-foreground">Average Rating</dt>
          <dd className="mt-1 font-medium text-foreground">{formatAverageRating(product.average_rating)}</dd>
        </div>
      </dl>

      <div className="mt-3 rounded-md border border-border/70 bg-background px-3 py-2">
        <p className="text-xs text-muted-foreground">Latest Capture</p>
        <p className="mt-1 text-sm font-medium text-foreground">{captureTime}</p>
      </div>

      <div className="mt-4 flex items-center justify-end">
        <Button type="button" size="sm" onClick={() => onAnalyze(product.id)}>
          Analyze
        </Button>
      </div>
    </article>
  );
}
