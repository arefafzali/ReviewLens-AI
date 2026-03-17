import React from "react";
import { render, screen } from "@testing-library/react";

import HomePage from "./page";

describe("HomePage", () => {
  it("renders scaffold headline", () => {
    render(<HomePage />);

    expect(screen.getByRole("heading", { name: "Analyst Workspace Scaffold" })).toBeInTheDocument();
    expect(screen.getByText(/url\/csv ingestion/i)).toBeInTheDocument();
  });
});
