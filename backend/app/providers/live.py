import json
import re
from typing import Any

import httpx

from app.models import ProductAnalysis, ProductFacts
from app.url_parser import AmazonLink


class ProviderError(RuntimeError):
    """A safe, user-facing external provider failure."""


def _parse_json_content(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderError("模型返回了无法解析的结构化结果") from exc
    if not isinstance(value, dict):
        raise ProviderError("模型返回结果不是 JSON 对象")
    return value


class RainforestProductProvider:
    endpoint = "https://api.rainforestapi.com/request"
    provider_name = "Rainforest"
    field_sources = {
        "title": "product.title",
        "category": "product.categories[-1].name",
        "price": "product.buybox_winner.price | product.price",
        "currency": "product.buybox_winner.price.currency | product.price.currency",
        "rating": "product.rating",
        "review_count": "product.ratings_total",
        "features": "product.feature_bullets",
        "specifications": "product.specifications",
        "evidence_texts": "product.description | product.feature_sections | product.a_plus_content | product.product_overview",
        "images": "product.images_flat | product.images[].link",
    }

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=httpx.Timeout(25.0, connect=10.0))

    def _collect_evidence_texts(self, product: dict[str, Any]) -> list[str]:
        evidence_keys = {
            "description",
            "feature_sections",
            "a_plus_content",
            "product_overview",
            "technical_details",
            "important_information",
            "product_description",
            "detail_bullets",
        }
        texts: list[str] = []

        def visit(value: Any, parent_key: str = "") -> None:
            if isinstance(value, str):
                text = re.sub(r"\s+", " ", value).strip()
                if text and (parent_key in evidence_keys or len(text) >= 18):
                    texts.append(text)
                return
            if isinstance(value, list):
                for item in value:
                    visit(item, parent_key)
                return
            if isinstance(value, dict):
                for key, nested in value.items():
                    visit(nested, str(key))

        for key in evidence_keys:
            if key in product:
                visit(product[key], key)

        deduped: list[str] = []
        seen: set[str] = set()
        for text in texts:
            normalized = text.lower()
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(text)
        return deduped[:40]

    def fetch(self, link: AmazonLink) -> ProductFacts:
        domain = link.marketplace_host
        response = self.client.get(
            self.endpoint,
            params={"api_key": self.api_key, "type": "product", "amazon_domain": domain, "asin": link.asin},
        )
        try:
            response.raise_for_status()
            product = response.json()["product"]
            if not isinstance(product, dict):
                raise TypeError("product must be an object")
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError("商品数据服务暂时不可用或未返回有效商品") from exc

        returned_asin = product.get("asin")
        if returned_asin and str(returned_asin).upper() != link.asin.upper():
            raise ProviderError(f"商品数据服务返回的 ASIN 与请求不一致：{returned_asin}")

        categories = [item for item in product.get("categories", []) if isinstance(item, dict)] if isinstance(product.get("categories", []), list) else []
        buybox = product.get("buybox_winner") if isinstance(product.get("buybox_winner"), dict) else {}
        price_value = buybox.get("price") or product.get("price") or {}
        price = price_value if isinstance(price_value, dict) else {"raw": str(price_value)}
        specifications = product.get("specifications") if isinstance(product.get("specifications"), list) else []
        specs = {
            str(item.get("name")): str(item.get("value"))
            for item in specifications
            if isinstance(item, dict) and item.get("name") and item.get("value")
        }
        images_flat = product.get("images_flat") if isinstance(product.get("images_flat"), str) else ""
        images = [item.strip() for item in images_flat.split(",") if item.strip()]
        if not images:
            image_items = product.get("images") if isinstance(product.get("images"), list) else []
            images = [str(item.get("link")) for item in image_items if isinstance(item, dict) and item.get("link")]
        feature_bullets = product.get("feature_bullets") if isinstance(product.get("feature_bullets"), list) else []
        raw_price = price.get("raw") or price.get("value")

        return ProductFacts(
            asin=link.asin,
            title=product.get("title") or "未命名商品",
            category=(categories[-1].get("name") if categories else "未分类"),
            price=str(raw_price) if raw_price is not None else None,
            currency=price.get("currency"),
            rating=product.get("rating"),
            review_count=product.get("ratings_total"),
            features=[str(item) for item in feature_bullets if str(item).strip()],
            specifications=specs,
            evidence_texts=self._collect_evidence_texts(product),
            images=images[:8],
            source_url=link.canonical_url,
        )


class QwenVisionProvider:
    endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    provider_name = "Qwen"

    def __init__(self, api_key: str, model: str = "qwen3-vl-plus", client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0))

    def analyze(self, images: list[str]) -> list[str]:
        if not images:
            return []
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": "分析这些电商商品图。只描述图片中可见且与购买决策相关的结构、材质、配件、尺寸标注和使用场景。不得猜测。输出 JSON：{\"findings\":[\"...\"]}",
            }
        ]
        content.extend({"type": "image_url", "image_url": {"url": url}} for url in images[:6])
        response = self.client.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": [{"role": "user", "content": content}], "response_format": {"type": "json_object"}},
        )
        try:
            response.raise_for_status()
            payload = _parse_json_content(response.json()["choices"][0]["message"]["content"])
            findings = [str(item) for item in payload.get("findings", []) if str(item).strip()]
            if not findings:
                raise ProviderError("图片分析服务返回的图片观察为空")
            return findings
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError("图片分析服务暂时不可用") from exc


class DeepSeekTextModel:
    endpoint = "https://api.deepseek.com/chat/completions"
    provider_name = "DeepSeek"

    def __init__(self, api_key: str, model: str = "deepseek-v4-flash", client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))

    def _request_json(self, prompt: str) -> dict[str, Any]:
        response = self.client.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是严谨的电商产品分析师。只能使用输入证据，不得虚构。输出合法 JSON，不要 Markdown。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},
            },
        )
        try:
            response.raise_for_status()
            return _parse_json_content(response.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError("DeepSeek 分析服务暂时不可用") from exc

    def _validate_analysis(self, payload: dict[str, Any]) -> ProductAnalysis:
        try:
            analysis = ProductAnalysis.model_validate(payload)
        except ValueError as exc:
            raise ProviderError("DeepSeek 分析服务暂时不可用") from exc

        required = (
            analysis.target_users,
            analysis.scenarios,
            analysis.pain_points,
            analysis.selling_points,
            analysis.visual_findings,
            analysis.voiceover.strip(),
        )
        if not all(required):
            raise ProviderError("DeepSeek 返回的分析内容为空或不完整")
        return analysis

    def _complete(self, prompt: str) -> ProductAnalysis:
        return self._validate_analysis(self._request_json(prompt))

    def analyze(self, facts: ProductFacts, visual_findings: list[str]) -> ProductAnalysis:
        schema = {
            "target_users": ["目标用户"],
            "scenarios": ["使用场景"],
            "pain_points": ["用户痛点"],
            "selling_points": ["必须可由证据支持的卖点"],
            "visual_findings": visual_findings,
            "voiceover": "150字以内中文口播，前5秒用问题或反差钩子",
        }
        return self._complete(
            "根据商品事实和图片观察完成产品分析。区分事实与推断，口播不得使用绝对化宣传。\n"
            f"商品事实：{facts.model_dump_json(exclude={'images'})}\n"
            f"图片观察：{json.dumps(visual_findings, ensure_ascii=False)}\n"
            f"输出格式：{json.dumps(schema, ensure_ascii=False)}"
        )

    def revise(self, facts: ProductFacts, analysis: ProductAnalysis, issue_messages: list[str]) -> ProductAnalysis:
        schema = {
            "target_users": ["目标用户，非空数组"],
            "scenarios": ["使用场景，非空数组"],
            "pain_points": ["用户痛点，非空数组"],
            "selling_points": ["必须可由证据支持的卖点，非空数组"],
            "visual_findings": ["图片观察，非空数组"],
            "voiceover": "150字以内中文口播，非空字符串",
        }
        payload = self._request_json(
            "修订以下分析，只解决质量问题，保持有证据的内容。口播不超过150字。\n"
            f"商品事实：{facts.model_dump_json(exclude={'images'})}\n"
            f"原分析：{analysis.model_dump_json()}\n"
            f"质量问题：{json.dumps(issue_messages, ensure_ascii=False)}\n"
            f"输出完整 JSON，必须包含以下所有字段且不得为空：{json.dumps(schema, ensure_ascii=False)}"
        )
        merged = analysis.model_dump(mode="json")
        merged.update({key: value for key, value in payload.items() if key in merged})
        return self._validate_analysis(merged)
