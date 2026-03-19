import React from "react";
import { render, screen } from "@testing-library/react";

import ProductDetailPage from "./page";

vi.mock("@/components/workspace/product-analysis-workspace", () => ({
  ProductAnalysisWorkspace: ({ productId }: { productId: string }) => (
    <div data-testid="product-analysis-workspace">Product {productId}</div>
  ),
}));

describe("ProductDetailPage", () => {
  it("renders product analysis workspace for a valid UUID route", () => {
    render(<ProductDetailPage params={{ id: "08f51446-b913-4f99-a6cc-0c7f84b49145" }} />);

    expect(screen.getByRole("heading", { name: "Product Analysis" })).toBeInTheDocument();
    expect(screen.getByTestId("product-analysis-workspace")).toBeInTheDocument();
  });

  it("renders clean invalid-id state for malformed product IDs", () => {
    render(<ProductDetailPage params={{ id: "not-a-uuid" }} />);

    expect(screen.getByRole("heading", { name: "Product Not Found" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid product identifier.");
    expect(screen.queryByTestId("product-analysis-workspace")).not.toBeInTheDocument();
  });
});
