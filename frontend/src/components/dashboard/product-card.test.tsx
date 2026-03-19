import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import type { ProductListItem } from "@/types/api";

import { ProductCard } from "./product-card";

function makeProduct(overrides: Partial<ProductListItem> = {}): ProductListItem {
  return {
    id: "product-1",
    workspace_id: "workspace-1",
    platform: "capterra",
    name: "PressPage",
    source_url: "https://www.capterra.com/p/164876/PressPage/reviews/",
    total_reviews: 17,
    average_rating: 4.59,
    chat_session_count: 2,
    latest_ingestion: {
      ingestion_run_id: "run-1",
      status: "success",
      outcome_code: "ok",
      completed_at: "2026-03-19T11:30:00Z",
    },
    updated_at: "2026-03-19T11:30:00Z",
    ...overrides,
  };
}

describe("ProductCard", () => {
  it("renders key product fields", () => {
    render(<ProductCard product={makeProduct()} onAnalyze={vi.fn()} />);

    expect(screen.getByText("PressPage")).toBeInTheDocument();
    expect(screen.getByText("Capterra - www.capterra.com")).toBeInTheDocument();
    expect(screen.getByText("17")).toBeInTheDocument();
    expect(screen.getByText("4.59 / 5")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze" })).toBeInTheDocument();
  });

  it("handles missing/partial fields safely", () => {
    render(
      <ProductCard
        product={makeProduct({
          platform: "",
          source_url: "invalid-url",
          average_rating: null,
          latest_ingestion: {
            completed_at: null,
          },
        })}
        onAnalyze={vi.fn()}
      />,
    );

    expect(screen.getByText("Unknown - unknown-source")).toBeInTheDocument();
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(screen.getByText("Capture pending")).toBeInTheDocument();
  });

  it("triggers analyze callback with product id", () => {
    const onAnalyze = vi.fn();
    render(<ProductCard product={makeProduct({ id: "product-xyz" })} onAnalyze={onAnalyze} />);

    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(onAnalyze).toHaveBeenCalledTimes(1);
    expect(onAnalyze).toHaveBeenCalledWith("product-xyz");
  });

  it("renders optional delete action slot", () => {
    const onDelete = vi.fn();
    render(
      <ProductCard
        product={makeProduct()}
        onAnalyze={vi.fn()}
        deleteAction={(
          <button type="button" onClick={onDelete}>
            Delete Product
          </button>
        )}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete Product" }));
    expect(onDelete).toHaveBeenCalledTimes(1);
  });
});
