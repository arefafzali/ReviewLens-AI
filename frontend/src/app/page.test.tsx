import React from "react";
import { render, screen } from "@testing-library/react";

import HomePage from "./page";

describe("HomePage", () => {
  it("renders core analyst workspace sections", () => {
    render(<HomePage />);

    expect(screen.getByRole("heading", { name: "Analyst Workspace" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ingestion Panel" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ingestion Summary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Suggested Questions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Analyst Chat" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Ingest from URL" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Upload CSV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run URL Ingestion" })).toBeInTheDocument();
    expect(screen.getAllByText("Loading")).toHaveLength(3);
  });
});
