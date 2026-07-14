import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { AnalysisTrace } from "./AnalysisTrace";
import type { TraceEvent } from "../types";

const events: TraceEvent[] = [
  {
    id: "product_fetch", stage: "PRODUCT_FETCH", title: "商品抓取", status: "completed",
    provider: "Rainforest", model: null, started_at: "2026-07-14T00:00:00Z",
    finished_at: "2026-07-14T00:00:01Z", duration_ms: 1000,
    input: { asin: "B0CXT9RSGQ" }, output: { title: "Camping chair" },
    field_sources: { title: "product.title" }, error: null,
  },
  {
    id: "vision_analysis", stage: "VISION_ANALYSIS", title: "图片分析", status: "failed",
    provider: "Qwen", model: "qwen3-vl-plus", started_at: "2026-07-14T00:00:01Z",
    finished_at: "2026-07-14T00:00:02Z", duration_ms: 1000,
    input: { image_count: 1 }, output: {}, field_sources: {}, error: "图片观察为空",
  },
];

test("renders trace steps in order and expands structured evidence", async () => {
  const user = userEvent.setup();
  render(<AnalysisTrace events={events} />);
  const buttons = screen.getAllByRole("button");
  expect(buttons.map((button) => button.textContent)).toEqual([
    expect.stringContaining("商品抓取"), expect.stringContaining("图片分析"),
  ]);
  await user.click(screen.getByRole("button", { name: /商品抓取/ }));
  expect(screen.getAllByText("Rainforest")).toHaveLength(2);
  expect(screen.getByText("product.title")).toBeInTheDocument();
  expect(screen.getByText(/Camping chair/)).toBeInTheDocument();
});

test("shows failed stage error without hiding previous evidence", () => {
  render(<AnalysisTrace events={events} />);
  expect(screen.getByText("图片观察为空")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /商品抓取/ })).toBeInTheDocument();
});

test("automatically expands a step when polling changes it to running", () => {
  const pending = { ...events[0], status: "pending" as const };
  const { rerender } = render(<AnalysisTrace events={[pending]} />);
  expect(screen.getByRole("button", { name: /商品抓取/ })).toHaveAttribute("aria-expanded", "false");

  rerender(<AnalysisTrace events={[{ ...pending, status: "running" }]} />);

  expect(screen.getByRole("button", { name: /商品抓取/ })).toHaveAttribute("aria-expanded", "true");
});
