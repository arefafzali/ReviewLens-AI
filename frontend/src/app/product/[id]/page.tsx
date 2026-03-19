import React from "react";
import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { ProductAnalysisWorkspace } from "@/components/workspace/product-analysis-workspace";

type ProductDetailPageProps = {
  params: {
    id: string;
  };
};

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

export default function ProductDetailPage({ params }: ProductDetailPageProps): ReactNode {
  if (!isUuid(params.id)) {
    return (
      <AppShell
        title="Product Not Found"
        subtitle="The requested product identifier is invalid or unavailable in this workspace."
      >
        <p className="rounded-md border border-border bg-card px-4 py-3 text-sm text-foreground" role="alert">
          Invalid product identifier.
        </p>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Product Analysis"
      subtitle="Review summary confidence, grounded starter prompts, and scoped analyst chat for a single product."
    >
      <ProductAnalysisWorkspace productId={params.id} />
    </AppShell>
  );
}
