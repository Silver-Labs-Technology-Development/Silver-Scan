"""Offline tests for publisher-provided artwork and market insight providers."""
from unittest.mock import patch
import pytest

from app import coverage as C


@pytest.fixture(autouse=True)
def clean_cache():
    C._CACHE.clear()
    yield
    C._CACHE.clear()


def test_article_thumbnail_requires_publisher_cdn_and_https():
    url="https://images.cointelegraph.com/images/370_aHR0cHM6Ly9leGFtcGxlLmNvbQ==.jpg"
    assert C._news_image(url,"Cointelegraph")==url
    assert C._news_image("http://cointelegraph.com/image.png","Cointelegraph") is None
    assert C._news_image("https://cointelegraph.com.evil.example/pic.png","Cointelegraph") is None
    assert C._news_image("https://example.invalid/news.png","Cointelegraph") is None
    assert C._news_image("https://cointelegraph.com/","Cointelegraph") is None
    assert C._news_image("javascript:alert(1)","Cointelegraph") is None


def test_news_rss_thumbnail_favicon_source_and_date(monkeypatch):
    monkeypatch.setattr(C, "FEEDS", {
        "Cointelegraph":("https://cointelegraph.com/rss","cointelegraph.com")
    })
    xml=b"""<rss xmlns:media="http://search.yahoo.com/mrss/"><channel>
    <item><title>Network development updates</title>
      <link>https://cointelegraph.com/news/research-article</link>
      <pubDate>Thu, 29 Oct 2026 12:00:00 GMT</pubDate>
      <media:thumbnail url="https://cointelegraph.com/img/article.webp"/>
    </item><item><title>No photo here</title>
      <link>https://cointelegraph.com/news/another-article</link>
    </item><item><title>Hostile image URL</title>
      <link>https://cointelegraph.com/news/hostile-photo</link>
      <media:thumbnail url="https://evil.invalid/images/photo.jpg"/>
    </item></channel></rss>"""
    with patch.object(C,"_fetch",return_value=xml):
        result=C.news(5)
    assert len(result["articles"])==3
    by_title={a["title"]:a for a in result["articles"]}
    assert by_title["Network development updates"]["thumbnail_url"]=="https://cointelegraph.com/img/article.webp"
    assert by_title["Network development updates"]["favicon_url"].startswith("https://cointelegraph.com")
    assert by_title["No photo here"]["thumbnail_url"] is None
    assert by_title["Hostile image URL"]["thumbnail_url"] is None
    assert by_title["Network development updates"]["published_at"] > 0


def test_trending_and_categories_keep_provider_identities():
    with patch.object(C,"_fetch",return_value={
        "coins":[{"item":{"id":"bitcoin-silver-2","name":"Bitcoin Silver",
                          "symbol":"btcs","market_cap_rank":4321}},
                 {"item":{"id":"malicious/coin","name":"Bad","symbol":"bad"}}]}):
        trending=C.cg_trending()
    assert trending["coins"][0]["id"]=="coingecko:bitcoin-silver-2"
    assert len(trending["coins"])==1
    assert trending["coins"][0]["market_status"]=="trending-search-unverified"
    with patch.object(C,"_fetch",return_value=[
        {"id":"layer-2","name":"Layer 2","market_cap":"1000000",
         "market_cap_change_24h":3.1,"volume_24h":50000}
    ]):
        categories=C.cg_categories(10)
    assert categories["categories"][0]["change_24h_pct"]==pytest.approx(3.1)
    assert categories["categories"][0]["market_cap_usd"]==pytest.approx(1_000_000)


def test_exchanges_and_defi_are_read_only_provider_snapshots():
    with patch.object(C,"_fetch",return_value=[
        {"id":"sample-venue","name":"Sample Venue","trust_score_rank":4,
         "trade_volume_24h_btc":"210.4","trust_score":8,
         "url":"https://example.net"},
        {"id":"bad-venue","name":"Bad Venue","url":"javascript:alert(1)"}
    ]):
        exchanges=C.cg_exchanges(1,20)
    assert exchanges["exchanges"][0]["rank"]==4
    assert exchanges["exchanges"][1]["website"] is None
    with patch.object(C,"_fetch",return_value={"data":{
        "defi_market_cap":"300000","trading_volume_24h":"20000",
        "defi_dominance":"2.4","defi_to_eth_ratio":"12.5",
        "top_coin_name":"Example token"}}):
        defi=C.cg_defi()
    assert defi["market_cap_usd"]==pytest.approx(300000)
    assert defi["dominance_pct"]==pytest.approx(2.4)
    assert defi["top_coin_name"]=="Example token"
