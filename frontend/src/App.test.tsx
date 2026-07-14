import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import App from "./App";
import * as api from "./api";


vi.mock("./api");

const completedJob = {
  id: "job-1",
  url: "https://amazon.com/dp/B0CXT9RSGQ",
  status: "completed" as const,
  stage: "COMPLETED",
  progress: 100,
  error: null,
  trace_events: [
    {
      id: "product_fetch", stage: "PRODUCT_FETCH" as const, title: "商品抓取", status: "completed" as const,
      provider: "Rainforest", model: null, started_at: "2026-07-14T00:00:00Z", finished_at: "2026-07-14T00:00:01Z",
      duration_ms: 1000, input: { asin: "B0CXT9RSGQ" }, output: { title: "VTOY 便携折叠露营椅" },
      field_sources: { title: "product.title" }, error: null,
    },
  ],
  result: {
    facts: {
      asin: "B0CXT9RSGQ",
      title: "VTOY 便携折叠露营椅",
      category: "户外露营椅",
      price: "$89.99",
      currency: "USD",
      rating: 4.4,
      review_count: 286,
      features: ["可折叠设计", "可调节遮阳篷"],
      specifications: { "承重": "300 lb" },
      images: ["https://example.com/chair.jpg"],
      source_url: "https://amazon.com/dp/B0CXT9RSGQ",
    },
    analysis: {
      target_users: ["露营爱好者"],
      scenarios: ["营地休息"],
      pain_points: ["烈日下缺少遮挡"],
      selling_points: ["可调节遮阳篷"],
      visual_findings: ["主图可见顶部遮阳篷"],
      voiceover: "户外坐下就被太阳追着晒？这把折叠椅自带遮阳篷，收起方便带走。",
    },
    quality: { score: 96, passed: true, evidence_coverage: 100, issues: [] },
  },
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T00:00:01Z",
};

beforeEach(() => {
  vi.mocked(api.getHealth).mockResolvedValue({ status: "ok", mode: "live" });
  vi.mocked(api.createJob).mockResolvedValue({ ...completedJob, status: "queued", result: null, progress: 0 });
  vi.mocked(api.getJob).mockResolvedValue(completedJob);
});

test("submits an Amazon link and renders the complete analysis", async () => {
  const user = userEvent.setup();
  render(<App />);

  await user.type(screen.getByLabelText("Amazon 商品链接"), completedJob.url);
  await user.click(screen.getByRole("button", { name: "开始分析" }));

  expect(await screen.findByText("VTOY 便携折叠露营椅")).toBeInTheDocument();
  expect(screen.getByText("目标用户")).toBeInTheDocument();
  expect(screen.getByText("质量评分")).toBeInTheDocument();
  expect(screen.getByText("96")).toBeInTheDocument();
  expect(screen.getByText(completedJob.result.analysis.voiceover)).toBeInTheDocument();
  expect(screen.getByText("分析过程")).toBeInTheDocument();
  expect(await screen.findByText("真实 API")).toBeInTheDocument();
  expect(api.createJob).toHaveBeenCalledWith(completedJob.url);
});

test("shows a useful error when the API rejects the request", async () => {
  vi.mocked(api.createJob).mockRejectedValue(new Error("仅支持公开的 Amazon HTTPS 商品链接"));
  const user = userEvent.setup();
  render(<App />);

  await user.type(screen.getByLabelText("Amazon 商品链接"), "https://example.com/product");
  await user.click(screen.getByRole("button", { name: "开始分析" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("仅支持公开的 Amazon HTTPS 商品链接");
});
