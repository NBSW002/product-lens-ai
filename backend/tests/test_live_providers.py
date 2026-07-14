import json

import httpx
import pytest

from app.models import ProductFacts
from app.providers.live import DeepSeekTextModel, ProviderError, QwenVisionProvider, RainforestProductProvider
from app.url_parser import parse_amazon_url


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_rainforest_provider_normalizes_product_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["asin"] == "B0CXT9RSGQ"
        assert request.url.params["api_key"] == "secret"
        return httpx.Response(
            200,
            json={
                "product": {
                    "asin": "B0CXT9RSGQ",
                    "title": "Camping chair",
                    "categories": [{"name": "Outdoor Chairs"}],
                    "buybox_winner": {"price": {"raw": "$89.99", "currency": "USD"}},
                    "rating": 4.5,
                    "ratings_total": 120,
                    "feature_bullets": ["Foldable", "Sun shade"],
                    "specifications": [{"name": "Material", "value": "Oxford cloth"}],
                    "images_flat": "https://img/1.jpg,https://img/2.jpg",
                }
            },
        )

    provider = RainforestProductProvider("secret", client=_client(handler))
    facts = provider.fetch(parse_amazon_url("https://amazon.com/dp/B0CXT9RSGQ"))

    assert facts.title == "Camping chair"
    assert facts.price == "$89.99"
    assert facts.specifications["Material"] == "Oxford cloth"
    assert len(facts.images) == 2
    assert provider.field_sources["title"] == "product.title"


def test_rainforest_provider_rejects_mismatched_asin() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"product": {"asin": "B000000000", "title": "Wrong product"}})

    provider = RainforestProductProvider("secret", client=_client(handler))

    with pytest.raises(ProviderError, match="ASIN"):
        provider.fetch(parse_amazon_url("https://amazon.com/dp/B0CXT9RSGQ"))


def test_qwen_vision_provider_requests_images_and_parses_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3-vl-plus"
        assert sum(item["type"] == "image_url" for item in payload["messages"][0]["content"]) == 2
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"findings":["可见遮阳篷","可见杯架"]}'}}]},
        )

    provider = QwenVisionProvider("qwen-key", client=_client(handler))

    assert provider.analyze(["https://img/1.jpg", "https://img/2.jpg"]) == ["可见遮阳篷", "可见杯架"]


def test_qwen_vision_provider_rejects_empty_findings() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"findings":[]}'}}]})

    provider = QwenVisionProvider("qwen-key", client=_client(handler))

    with pytest.raises(ProviderError, match="图片观察为空"):
        provider.analyze(["https://img/1.jpg"])


def test_deepseek_model_parses_analysis_json() -> None:
    content = {
        "target_users": ["露营用户"],
        "scenarios": ["营地"],
        "pain_points": ["缺少遮阳"],
        "selling_points": ["可折叠"],
        "visual_findings": ["可见遮阳篷"],
        "voiceover": "露营总被太阳晒？这把可折叠座椅自带遮阳设计，收纳后方便携带。",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek-v4-flash"
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]})

    model = DeepSeekTextModel("deep-key", client=_client(handler))
    facts = ProductFacts(
        asin="B0CXT9RSGQ",
        title="折叠椅",
        category="户外椅",
        features=["可折叠"],
        source_url="https://amazon.com/dp/B0CXT9RSGQ",
    )

    analysis = model.analyze(facts, ["可见遮阳篷"])

    assert analysis.target_users == ["露营用户"]
    assert analysis.voiceover.startswith("露营")


def test_deepseek_model_rejects_empty_analysis_content() -> None:
    empty_content = {
        "target_users": [],
        "scenarios": [],
        "pain_points": [],
        "selling_points": [],
        "visual_findings": [],
        "voiceover": "",
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(empty_content)}}]},
        )

    model = DeepSeekTextModel("deep-key", client=_client(handler))
    facts = ProductFacts(
        asin="B0CXT9RSGQ",
        title="折叠椅",
        category="户外椅",
        features=["可折叠"],
        source_url="https://amazon.com/dp/B0CXT9RSGQ",
    )

    with pytest.raises(ProviderError, match="内容为空"):
        model.analyze(facts, ["可见遮阳篷"])
