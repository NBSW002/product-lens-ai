import pytest

from app.models import ProductAnalysis
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
