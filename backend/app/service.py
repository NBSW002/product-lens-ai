from collections.abc import Callable
from typing import Protocol

from app.models import AnalysisResult, ProductAnalysis, ProductFacts
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


class AnalysisService:
    def __init__(self, product_provider: ProductProvider, vision_provider: VisionProvider, text_model: TextModel) -> None:
        self.product_provider = product_provider
        self.vision_provider = vision_provider
        self.text_model = text_model
        self.quality_checker = QualityChecker()

    def run(self, url: str, on_progress: ProgressCallback | None = None) -> AnalysisResult:
        report = on_progress or (lambda _stage, _progress: None)
        report("VALIDATING", 5)
        link = parse_amazon_url(url)

        report("FETCHING_PRODUCT", 20)
        facts = self.product_provider.fetch(link)

        report("ANALYZING_IMAGES", 45)
        visual_findings = self.vision_provider.analyze(facts.images)

        report("ANALYZING_PRODUCT", 65)
        analysis = self.text_model.analyze(facts, visual_findings)

        report("CHECKING_QUALITY", 85)
        quality = self.quality_checker.check(facts, analysis)
        if not quality.passed:
            report("REVISING_CONTENT", 92)
            analysis = self.text_model.revise(facts, analysis, [issue.message for issue in quality.issues])
            quality = self.quality_checker.check(facts, analysis)

        report("COMPLETED", 100)
        return AnalysisResult(facts=facts, analysis=analysis, quality=quality)

