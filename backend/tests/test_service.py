from app.providers import DemoProductProvider, DemoTextModel, DemoVisionProvider
from app.service import AnalysisService


def test_demo_pipeline_returns_grounded_result_and_progress() -> None:
    events: list[tuple[str, int]] = []
    service = AnalysisService(
        product_provider=DemoProductProvider(),
        vision_provider=DemoVisionProvider(),
        text_model=DemoTextModel(),
    )

    result = service.run(
        "https://www.amazon.com/dp/B0CXT9RSGQ",
        on_progress=lambda stage, progress: events.append((stage, progress)),
    )

    assert result.facts.asin == "B0CXT9RSGQ"
    assert result.facts.images[0].startswith("data:image/svg+xml")
    assert result.analysis.visual_findings
    assert result.quality.passed is True
    assert len(result.analysis.voiceover) <= 150
    assert events[0][0] == "VALIDATING"
    assert events[-1] == ("COMPLETED", 100)
    assert [progress for _, progress in events] == sorted(progress for _, progress in events)
