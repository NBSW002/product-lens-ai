export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface ProductFacts {
  asin: string;
  title: string;
  category: string;
  price: string | null;
  currency: string | null;
  rating: number | null;
  review_count: number | null;
  features: string[];
  specifications: Record<string, string>;
  images: string[];
  source_url: string;
}

export interface ProductAnalysis {
  target_users: string[];
  scenarios: string[];
  pain_points: string[];
  selling_points: string[];
  visual_findings: string[];
  voiceover: string;
}

export interface QualityIssue {
  code: string;
  severity: "low" | "medium" | "high";
  message: string;
  suggestion: string;
}

export interface QualityReport {
  score: number;
  passed: boolean;
  evidence_coverage: number;
  issues: QualityIssue[];
}

export interface AnalysisResult {
  facts: ProductFacts;
  analysis: ProductAnalysis;
  quality: QualityReport;
}

export type TraceStage = "PRODUCT_FETCH" | "VISION_ANALYSIS" | "TEXT_DRAFT" | "QUALITY_CHECK" | "TEXT_REVISION" | "FINALIZE";
export type TraceStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export interface TraceEvent {
  id: string;
  stage: TraceStage;
  title: string;
  status: TraceStatus;
  provider: string;
  model: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  field_sources: Record<string, string>;
  error: string | null;
}

export interface HealthStatus {
  status: string;
  mode: "demo" | "live" | string;
}

export interface Job {
  id: string;
  url: string;
  status: JobStatus;
  stage: string;
  progress: number;
  result: AnalysisResult | null;
  error: string | null;
  trace_events: TraceEvent[];
  created_at: string;
  updated_at: string;
}
