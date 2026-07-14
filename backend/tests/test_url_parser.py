import pytest

from app.url_parser import InvalidAmazonUrl, parse_amazon_url


@pytest.mark.parametrize(
    ("url", "asin"),
    [
        ("https://www.amazon.com/dp/B0F6YQ96L5", "B0F6YQ96L5"),
        ("https://amazon.com/gp/product/B0CXT9RSGQ?ref_=abc", "B0CXT9RSGQ"),
        (
            "https://www.amazon.com/VTOY-Chairs%EF%BC%8CCamping/dp/B0CXT9RSGQ",
            "B0CXT9RSGQ",
        ),
        ("https://www.amazon.co.uk/dp/B012345678", "B012345678"),
    ],
)
def test_parse_amazon_product_urls(url: str, asin: str) -> None:
    parsed = parse_amazon_url(url)

    assert parsed.asin == asin
    assert parsed.canonical_url.endswith(f"/dp/{asin}")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/dp/B0F6YQ96L5",
        "https://amazon.evil.example/dp/B0F6YQ96L5",
        "https://www.amazon.com/dp/not-an-asin",
        "javascript:alert(1)",
        "",
    ],
)
def test_rejects_untrusted_or_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidAmazonUrl):
        parse_amazon_url(url)

