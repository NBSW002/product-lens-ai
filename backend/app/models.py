from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ProductFacts(BaseModel):
    asin: str
    title: str
    category: str
    price: str | None = None
    currency: str | None = None
    rating: float | None = None
    review_count: int | None = None
    features: list[str] = Field(default_factory=list)
    specifications: dict[str, str] = Field(default_factory=dict)
    images: list[str] = Field(default_factory=list)
    source_url: str


class ProductAnalysis(BaseModel):
    target_users: list[str]
    scenarios: list[str]
    pain_points: list[str]
    selling_points: list[str]
    visual_findings: list[str]
    voiceover: str


class QualityIssue(BaseModel):
    code: str
    severity: Literal["low", "medium", "high"]
    message: str
    suggestion: str


class QualityReport(BaseModel):
    score: int
    passed: bool
    evidence_coverage: int
    issues: list[QualityIssue] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    facts: ProductFacts
    analysis: ProductAnalysis
    quality: QualityReport


class CreateJobRequest(BaseModel):
    url: str


class Job(BaseModel):
    id: str
    url: str
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    stage: str = "QUEUED"
    progress: int = 0
    result: AnalysisResult | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

