import pytest

from app.models import ProductAnalysis, ProductFacts, QualityIssue, QualityReport
from app.providers import DemoProductProvider, DemoTextModel, DemoVisionProvider
from app.service import AnalysisService


def test_demo_pipeline_returns_grounded_result_and_progress() -> None:
    events: list[tuple[str, int]] = []
    traces: list[tuple[str, str, dict[str, object]]] = []
    service = AnalysisService(
        product_provider=DemoProductProvider(),
        vision_provider=DemoVisionProvider(),
        text_model=DemoTextModel(),
    )

    result = service.run(
        "https://www.amazon.com/dp/B0CXT9RSGQ",
        on_progress=lambda stage, progress: events.append((stage, progress)),
        on_trace=lambda action, stage, payload: traces.append((action, stage, payload)),
    )

    assert result.facts.asin == "B0CXT9RSGQ"
    assert result.facts.images[0].startswith("data:image/svg+xml")
    assert result.analysis.visual_findings
    assert result.quality.passed is True
    assert len(result.analysis.voiceover) <= 150
    assert events[0][0] == "VALIDATING"
    assert events[-1] == ("COMPLETED", 100)
    assert [progress for _, progress in events] == sorted(progress for _, progress in events)
    assert [(action, stage) for action, stage, _ in traces] == [
        ("start", "PRODUCT_FETCH"),
        ("complete", "PRODUCT_FETCH"),
        ("start", "VISION_ANALYSIS"),
        ("complete", "VISION_ANALYSIS"),
        ("start", "TEXT_DRAFT"),
        ("complete", "TEXT_DRAFT"),
        ("start", "QUALITY_CHECK"),
        ("complete", "QUALITY_CHECK"),
        ("skip", "TEXT_REVISION"),
        ("start", "FINALIZE"),
        ("complete", "FINALIZE"),
    ]


def test_pipeline_failure_keeps_completed_trace_and_skips_later_stages() -> None:
    class BrokenVision:
        def analyze(self, _images: list[str]) -> list[str]:
            raise RuntimeError("vision unavailable")

    traces: list[tuple[str, str, dict[str, object]]] = []
    service = AnalysisService(DemoProductProvider(), BrokenVision(), DemoTextModel())

    with pytest.raises(RuntimeError, match="vision unavailable"):
        service.run(
            "https://www.amazon.com/dp/B0CXT9RSGQ",
            on_trace=lambda action, stage, payload: traces.append((action, stage, payload)),
        )

    assert ("complete", "PRODUCT_FETCH") in [(action, stage) for action, stage, _ in traces]
    assert ("fail", "VISION_ANALYSIS") in [(action, stage) for action, stage, _ in traces]
    assert [(action, stage) for action, stage, _ in traces][-4:] == [
        ("skip", "TEXT_DRAFT"),
        ("skip", "QUALITY_CHECK"),
        ("skip", "TEXT_REVISION"),
        ("skip", "FINALIZE"),
    ]


def test_pipeline_preserves_draft_when_revision_is_required() -> None:
    class RevisingTextModel:
        def analyze(self, _facts, visual_findings: list[str]) -> ProductAnalysis:
            return ProductAnalysis(
                target_users=["露营用户"],
                scenarios=["营地"],
                pain_points=["携带不便"],
                selling_points=["不存在功能"],
                visual_findings=visual_findings,
                voiceover="露营装备总是难带吗？这款产品提供不存在功能。",
            )

        def revise(self, _facts, _analysis, _issues: list[str]) -> ProductAnalysis:
            return ProductAnalysis(
                target_users=["露营用户"],
                scenarios=["营地"],
                pain_points=["携带不便"],
                selling_points=["可折叠设计"],
                visual_findings=["主图可见顶部遮阳篷"],
                voiceover="露营装备总是难带吗？这把椅子采用可折叠设计，收起后更方便携带。",
            )

    traces: list[tuple[str, str, dict[str, object]]] = []
    result = AnalysisService(DemoProductProvider(), DemoVisionProvider(), RevisingTextModel()).run(
        "https://www.amazon.com/dp/B0CXT9RSGQ",
        on_trace=lambda action, stage, payload: traces.append((action, stage, payload)),
    )

    draft = next(payload["output"] for action, stage, payload in traces if action == "complete" and stage == "TEXT_DRAFT")
    revision = next(payload["output"] for action, stage, payload in traces if action == "complete" and stage == "TEXT_REVISION")
    assert draft["selling_points"] == ["不存在功能"]
    assert revision["selling_points"] == ["可折叠设计"]
    assert result.quality.passed is True


def test_pipeline_applies_deterministic_fallback_when_revision_keeps_unsupported_claims() -> None:
    class ProductProvider:
        def fetch(self, _link) -> ProductFacts:
            return ProductFacts(
                asin="B07FZ8S74R",
                title="Echo Dot smart speaker",
                category="Smart speakers",
                features=["Voice control your music"],
                evidence_texts=["Voice control your music from Amazon Music, Apple Music, Spotify, and others."],
                images=["https://example.com/echo.jpg"],
                source_url="https://amazon.com/dp/B07FZ8S74R",
            )

    class VisionProvider:
        def analyze(self, _images: list[str]) -> list[str]:
            return ["Product image shows a compact smart speaker"]

    class TextModel:
        def analyze(self, _facts, visual_findings: list[str]) -> ProductAnalysis:
            return ProductAnalysis(
                target_users=["Smart speaker users"],
                scenarios=["Music playback"],
                pain_points=["Hands-free control is needed"],
                selling_points=["Unsupported home automation claim"],
                visual_findings=visual_findings,
                voiceover="Need hands-free control? This speaker can help with music playback.",
            )

        def revise(self, _facts, analysis: ProductAnalysis, _issues: list[str]) -> ProductAnalysis:
            return analysis.model_copy(update={"selling_points": ["Unsupported home automation claim"]})

    result = AnalysisService(ProductProvider(), VisionProvider(), TextModel()).run("https://www.amazon.com/dp/B07FZ8S74R")

    assert result.quality.passed is True
    assert "Unsupported home automation claim" not in result.analysis.selling_points
    assert "Voice control your music" in result.analysis.selling_points


def test_first_quality_exception_fails_active_stage_and_skips_later_stages() -> None:
    class BrokenQualityChecker:
        def check(self, _facts, _analysis):
            raise RuntimeError("quality exploded")

    traces: list[tuple[str, str, dict[str, object]]] = []
    service = AnalysisService(DemoProductProvider(), DemoVisionProvider(), DemoTextModel())
    service.quality_checker = BrokenQualityChecker()  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="quality exploded"):
        service.run(
            "https://www.amazon.com/dp/B0CXT9RSGQ",
            on_trace=lambda action, stage, payload: traces.append((action, stage, payload)),
        )

    assert [(action, stage) for action, stage, _ in traces][-3:] == [
        ("fail", "QUALITY_CHECK"),
        ("skip", "TEXT_REVISION"),
        ("skip", "FINALIZE"),
    ]


def test_second_quality_exception_fails_quality_and_skips_finalize() -> None:
    class RevisionModel:
        def analyze(self, _facts, visual_findings):
            return ProductAnalysis(
                target_users=["用户"], scenarios=["场景"], pain_points=["痛点"],
                selling_points=["不存在功能"], visual_findings=visual_findings, voiceover="还在苦恼吗？不存在功能。",
            )

        def revise(self, _facts, _analysis, _issues):
            return ProductAnalysis(
                target_users=["用户"], scenarios=["场景"], pain_points=["痛点"],
                selling_points=["可折叠设计"], visual_findings=["主图可见顶部遮阳篷"], voiceover="还在苦恼吗？采用可折叠设计。",
            )

    class BrokenSecondQualityChecker:
        calls = 0

        def check(self, _facts, _analysis):
            self.calls += 1
            if self.calls == 1:
                return QualityReport(
                    score=0, passed=False, evidence_coverage=0,
                    issues=[QualityIssue(code="TEST", severity="high", message="需修订", suggestion="修订")],
                )
            raise RuntimeError("second quality exploded")

    traces: list[tuple[str, str, dict[str, object]]] = []
    service = AnalysisService(DemoProductProvider(), DemoVisionProvider(), RevisionModel())
    service.quality_checker = BrokenSecondQualityChecker()  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="second quality exploded"):
        service.run(
            "https://www.amazon.com/dp/B0CXT9RSGQ",
            on_trace=lambda action, stage, payload: traces.append((action, stage, payload)),
        )

    assert [(action, stage) for action, stage, _ in traces][-2:] == [
        ("fail", "QUALITY_CHECK"),
        ("skip", "FINALIZE"),
    ]
