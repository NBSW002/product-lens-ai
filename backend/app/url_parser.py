from dataclasses import dataclass
import re
from urllib.parse import urlparse


ASIN_PATTERN = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE)
AMAZON_HOST_PATTERN = re.compile(
    r"^(?:www\.)?amazon\.(?:com|co\.uk|de|fr|it|es|ca|com\.au|co\.jp)$",
    re.IGNORECASE,
)


class InvalidAmazonUrl(ValueError):
    """Raised when a URL is not a supported public Amazon product URL."""


@dataclass(frozen=True, slots=True)
class AmazonLink:
    original_url: str
    asin: str
    marketplace_host: str
    canonical_url: str


def parse_amazon_url(url: str) -> AmazonLink:
    try:
        parsed = urlparse(url.strip())
    except (AttributeError, ValueError) as exc:
        raise InvalidAmazonUrl("请输入有效的 Amazon 商品链接") from exc

    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not AMAZON_HOST_PATTERN.fullmatch(host):
        raise InvalidAmazonUrl("仅支持公开的 Amazon HTTPS 商品链接")

    match = ASIN_PATTERN.search(parsed.path)
    if not match:
        raise InvalidAmazonUrl("链接中未找到有效的 10 位 ASIN")

    asin = match.group(1).upper()
    canonical_host = host.removeprefix("www.")
    return AmazonLink(
        original_url=url,
        asin=asin,
        marketplace_host=canonical_host,
        canonical_url=f"https://{canonical_host}/dp/{asin}",
    )

