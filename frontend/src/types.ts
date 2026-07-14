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

export interface Job {
  id: string;
  url: string;
  status: JobStatus;
  stage: string;
  progress: number;
  result: AnalysisResult | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

