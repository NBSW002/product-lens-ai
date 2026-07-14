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

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=httpx.Timeout(25.0, connect=10.0))

    def fetch(self, link: AmazonLink) -> ProductFacts:
        domain = link.marketplace_host
        response = self.client.get(
            self.endpoint,
            params={"api_key": self.api_key, "type": "product", "amazon_domain": domain, "asin": link.asin},
        )
        try:
            response.raise_for_status()
            product = response.json()["product"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError("商品数据服务暂时不可用或未返回有效商品") from exc

        categories = product.get("categories") or []
        buybox = product.get("buybox_winner") or {}
        price = buybox.get("price") or product.get("price") or {}
        specs = {
            str(item.get("name")): str(item.get("value"))
            for item in product.get("specifications") or []
            if item.get("name") and item.get("value")
        }
        images_flat = product.get("images_flat") or ""
        images = [item.strip() for item in images_flat.split(",") if item.strip()]
        if not images:
            images = [item.get("link") for item in product.get("images") or [] if item.get("link")]

        return ProductFacts(
            asin=link.asin,
            title=product.get("title") or "未命名商品",
            category=(categories[-1].get("name") if categories else "未分类"),
            price=price.get("raw") or price.get("value"),
            currency=price.get("currency"),
            rating=product.get("rating"),
            review_count=product.get("ratings_total"),
            features=product.get("feature_bullets") or [],
            specifications=specs,
            images=images[:8],
            source_url=link.canonical_url,
        )


class QwenVisionProvider:
    endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

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
            return [str(item) for item in payload.get("findings", []) if str(item).strip()]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError("图片分析服务暂时不可用") from exc


class DeepSeekTextModel:
    endpoint = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key: str, model: str = "deepseek-v4-flash", client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))

    def _complete(self, prompt: str) -> ProductAnalysis:
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
            payload = _parse_json_content(response.json()["choices"][0]["message"]["content"])
            return ProductAnalysis.model_validate(payload)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError("DeepSeek 分析服务暂时不可用") from exc

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
        return self._complete(
            "修订以下分析，只解决质量问题，保持有证据的内容。口播不超过150字。\n"
            f"商品事实：{facts.model_dump_json(exclude={'images'})}\n"
            f"原分析：{analysis.model_dump_json()}\n"
            f"质量问题：{json.dumps(issue_messages, ensure_ascii=False)}\n"
            "输出与原分析完全相同的 JSON 字段。"
        )

