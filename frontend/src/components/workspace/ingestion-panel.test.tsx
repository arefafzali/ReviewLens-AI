import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import { IngestionPanel } from "./ingestion-panel";

describe("IngestionPanel", () => {
  it("shows validation error for invalid URL submission", async () => {
    render(<IngestionPanel />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "not-a-url" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Prepare URL Ingestion" }));

    expect(await screen.findByText(/enter a valid url/i)).toBeInTheDocument();
  });

  it("accepts valid URL and shows ready message", async () => {
    render(<IngestionPanel />);

    fireEvent.change(screen.getByLabelText(/review page url/i), {
      target: { value: "https://example.com/reviews" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Prepare URL Ingestion" }));

    expect(await screen.findByText(/url payload ready for backend integration/i)).toBeInTheDocument();
  });

  it("shows CSV validation message when file is missing", async () => {
    render(<IngestionPanel />);

    fireEvent.click(screen.getByRole("tab", { name: "Upload CSV" }));
    fireEvent.click(screen.getByRole("button", { name: "Prepare CSV Ingestion" }));

    expect(await screen.findByText(/select a csv file/i)).toBeInTheDocument();
  });

  it("rejects non-csv uploads", async () => {
    render(<IngestionPanel />);

    fireEvent.click(screen.getByRole("tab", { name: "Upload CSV" }));
    const input = screen.getByLabelText(/review csv file/i);
    const txtFile = new File(["hello"], "reviews.txt", { type: "text/plain" });

    fireEvent.change(input, { target: { files: [txtFile] } });
    fireEvent.click(screen.getByRole("button", { name: "Prepare CSV Ingestion" }));

    expect(await screen.findByText(/upload a .csv file/i)).toBeInTheDocument();
  });
});
