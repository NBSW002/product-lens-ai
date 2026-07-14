from collections.abc import Callable
from typing import Protocol

from app.models import AnalysisResult, ProductAnalysis, ProductFacts, TraceStage
from app.quality import QualityChecker
from app.url_parser import AmazonLink, parse_amazon_url


class ProductProvider(Protocol):
    def fetch(self, link: AmazonLink) -> ProductFacts: ...


class VisionProvider(Protocol):
    def analyze(self, images: list[str]) -> list[str]: ...


class TextModel(Protocol):
    def analyze(self, facts: ProductFacts, visual_findings: list[str]) -> ProductAnalysis: ...
    def revise(self, facts: ProductFacts, analysis: ProductAnalysis, issue_messages: list[str]) -> ProductAnalysis: ...


ProgressCallback = Callable[[str, int], None]
TraceCallback = Callable[[str, TraceStage, dict[str, object]], None]


class AnalysisService:
    def __init__(self, product_provider: ProductProvider, vision_provider: VisionProvider, text_model: TextModel) -> None:
        self.product_provider = product_provider
        self.vision_provider = vision_provider
        self.text_model = text_model
        self.quality_checker = QualityChecker()

    def run(
        self,
        url: str,
        on_progress: ProgressCallback | None = None,
        on_trace: TraceCallback | None = None,
    ) -> AnalysisResult:
        report = on_progress or (lambda _stage, _progress: None)
        trace = on_trace or (lambda _action, _stage, _payload: None)

        def fail_stage(stage: TraceStage, exc: Exception, later: list[TraceStage]) -> None:
            trace("fail", stage, {"error": str(exc)})
            for later_stage in later:
                trace("skip", later_stage, {"reason": f"因 {stage} 失败而跳过"})

        report("VALIDATING", 5)
        link = parse_amazon_url(url)

        report("FETCHING_PRODUCT", 20)
        trace(
            "start",
            "PRODUCT_FETCH",
            {"input": {"asin": link.asin, "amazon_domain": link.marketplace_host, "url": link.canonical_url}},
        )
        try:
            facts = self.product_provider.fetch(link)
        except Exception as exc:
            fail_stage(
                "PRODUCT_FETCH",
                exc,
                ["VISION_ANALYSIS", "TEXT_DRAFT", "QUALITY_CHECK", "TEXT_REVISION", "FINALIZE"],
            )
            raise
        trace(
            "complete",
            "PRODUCT_FETCH",
            {
                "output": facts.model_dump(mode="json"),
                "field_sources": getattr(self.product_provider, "field_sources", {}),
            },
        )

        report("ANALYZING_IMAGES", 45)
        trace(
            "start",
            "VISION_ANALYSIS",
            {"input": {"image_count": min(6, len(facts.images)), "images": facts.images[:6]}},
        )
        try:
            visual_findings = self.vision_provider.analyze(facts.images)
            if not visual_findings:
                raise RuntimeError("图片分析未返回任何可验证观察")
        except Exception as exc:
            fail_stage("VISION_ANALYSIS", exc, ["TEXT_DRAFT", "QUALITY_CHECK", "TEXT_REVISION", "FINALIZE"])
            raise
        trace("complete", "VISION_ANALYSIS", {"output": {"findings": visual_findings}})

        report("ANALYZING_PRODUCT", 65)
        trace(
            "start",
            "TEXT_DRAFT",
            {"input": {"facts": facts.model_dump(mode="json", exclude={"images"}), "visual_findings": visual_findings}},
        )
        try:
            analysis = self.text_model.analyze(facts, visual_findings)
        except Exception as exc:
            fail_stage("TEXT_DRAFT", exc, ["QUALITY_CHECK", "TEXT_REVISION", "FINALIZE"])
            raise
        trace("complete", "TEXT_DRAFT", {"output": analysis.model_dump(mode="json")})

        report("CHECKING_QUALITY", 85)
        trace("start", "QUALITY_CHECK", {"input": {"draft": analysis.model_dump(mode="json")}})
        try:
            quality = self.quality_checker.check(facts, analysis)
        except Exception as exc:
            fail_stage("QUALITY_CHECK", exc, ["TEXT_REVISION", "FINALIZE"])
            raise
        initial_quality = quality.model_dump(mode="json")
        trace("complete", "QUALITY_CHECK", {"output": {"initial": initial_quality}})
        if not quality.passed:
            report("REVISING_CONTENT", 92)
            issue_messages = [issue.message for issue in quality.issues]
            trace(
                "start",
                "TEXT_REVISION",
                {"input": {"draft": analysis.model_dump(mode="json"), "quality_issues": issue_messages}},
            )
            try:
                analysis = self.text_model.revise(facts, analysis, issue_messages)
            except Exception as exc:
                fail_stage("TEXT_REVISION", exc, ["FINALIZE"])
                raise
            fallback_applied = False
            try:
                quality = self.quality_checker.check(facts, analysis)
                if not quality.passed and any(issue.code == "UNSUPPORTED_CLAIM" for issue in quality.issues):
                    repaired = self.quality_checker.repair_unsupported_claims(facts, analysis)
                    if repaired.selling_points != analysis.selling_points:
                        analysis = repaired
                        quality = self.quality_checker.check(facts, analysis)
                        fallback_applied = True
            except Exception as exc:
                fail_stage("QUALITY_CHECK", exc, ["FINALIZE"])
                raise
            trace("complete", "TEXT_REVISION", {"output": analysis.model_dump(mode="json"), "fallback_applied": fallback_applied})
            trace(
                "complete",
                "QUALITY_CHECK",
                {"output": {"initial": initial_quality, "final": quality.model_dump(mode="json")}},
            )
        else:
            trace("skip", "TEXT_REVISION", {"reason": "初稿已通过质量检查，无需修订"})

        trace(
            "start",
            "FINALIZE",
            {"input": {"quality": quality.model_dump(mode="json")}},
        )
        if not quality.passed:
            error = RuntimeError("自动修订后仍未通过完整性与证据检查")
            trace("fail", "FINALIZE", {"error": str(error)})
            raise error

        report("COMPLETED", 100)
        result = AnalysisResult(facts=facts, analysis=analysis, quality=quality)
        trace(
            "complete",
            "FINALIZE",
            {"output": {"status": "ready", "quality_score": quality.score, "evidence_coverage": quality.evidence_coverage}},
        )
        return result
