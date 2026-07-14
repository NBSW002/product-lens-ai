from app.models import ProductAnalysis, ProductFacts
from app.quality import QualityChecker, chinese_length


def _facts() -> ProductFacts:
    return ProductFacts(
        asin="B0CXT9RSGQ",
        title="便携折叠露营椅",
        category="户外椅",
        price="$89.99",
        currency="USD",
        features=["可折叠", "带遮阳篷", "杯架"],
        specifications={"承重": "300 lb", "材质": "牛津布"},
        images=["https://example.com/chair.jpg"],
        source_url="https://amazon.com/dp/B0CXT9RSGQ",
    )


def test_quality_checker_flags_exaggeration_and_unsupported_claims() -> None:
    analysis = ProductAnalysis(
        target_users=["露营爱好者"],
        scenarios=["露营"],
        pain_points=["烈日下缺少遮挡"],
        selling_points=["全球第一且百分百防晒", "内置冰箱"],
        visual_findings=["图片可见顶部遮阳篷"],
        voiceover="买它！全球第一且百分百防晒，还内置冰箱，错过后悔一辈子！",
    )

    report = QualityChecker().check(_facts(), analysis)

    assert report.score < 80
    assert any(issue.code == "EXAGGERATION" for issue in report.issues)
    assert any(issue.code == "UNSUPPORTED_CLAIM" for issue in report.issues)


def test_quality_checker_accepts_grounded_short_script() -> None:
    script = "露营一坐下就被太阳追着晒？这把折叠椅自带遮阳篷，杯架随手放饮料，收起后方便带走，适合营地和庭院休息。"
    analysis = ProductAnalysis(
        target_users=["露营爱好者"],
        scenarios=["露营", "庭院休息"],
        pain_points=["烈日下缺少遮挡"],
        selling_points=["可折叠", "带遮阳篷", "带杯架"],
        visual_findings=["图片可见顶部遮阳篷"],
        voiceover=script,
    )

    report = QualityChecker().check(_facts(), analysis)

    assert chinese_length(script) <= 150
    assert report.score >= 80
    assert report.passed is True

