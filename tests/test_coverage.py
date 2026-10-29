"""Deterministic offline verification of broad market coverage/news/mining adapters."""
import math
from unittest.mock import patch

import pytest
from app import coverage as C
from app import market_data as M


@pytest.fixture(autouse=True)
def empty_cache():
    C._CACHE.clear()
    yield
    C._CACHE.clear()


def test_low_rank_btcs_catalog_search_keeps_provider_id():
    catalog = [
        {"id": "some-bitcoin-silver-fork", "name": "Bitcoin Silver Clone", "symbol": "BTCS"},
        {"id": "bitcoin-silver-2", "name": "Bitcoin Silver", "symbol": "BTCS"},
    ] + [
        {"id": f"coin-{n}", "name": f"Coin {n}", "symbol": f"c{n}"}
        for n in range(500)
    ]
    with patch.object(C, "_fetch", return_value=catalog):
        data = C.cg_catalog_search("BTCS")
    assert data["matches"][0]["id"] == "coingecko:bitcoin-silver-2"
    assert data["catalog_count"] == 502
    assert all(x["market_status"] == "unverified" for x in data["matches"])


def test_active_coin_gecko_page_only_returns_positive_volume_and_price():
    raw=[
        {"id":"bitcoin-silver-2", "name":"Bitcoin Silver", "symbol":"btcs",
         "current_price":0.005,"total_volume":87, "market_cap_rank":5000},
        {"id":"stale-token","current_price":0.5,"total_volume":0},
        {"id":"unpriced","current_price":0,"total_volume":1},
    ]
    with patch.object(C,"_fetch",return_value=raw):
        data=C.cg_market_page(15,100)
    assert data["page"]==15
    assert [a["id"] for a in data["assets"]]==["coingecko:bitcoin-silver-2"]
    assert data["assets"][0]["market_status"]=="provider-reported-volume"


def test_cmc_pagination_keeps_cmc_identity_without_ticker_merging(monkeypatch):
    monkeypatch.delenv("CMC_API_KEY",raising=False)
    response={"status":{"error_code":0},"data":[
        {"id":123,"name":"Coin X","symbol":"X","cmc_rank":4000,
         "quote":{"USD":{"price":1.25,"volume_24h":1000,"market_cap":4000,"percent_change_24h":3}}},
        {"id":124,"name":"Dead","symbol":"X",
         "quote":{"USD":{"price":2,"volume_24h":0}}},
    ]}
    with patch.object(C,"_fetch",return_value=response) as f:
        data=C.cmc_active(2,100)
    assert data["source"]=="CoinMarketCap"
    assert [a["id"] for a in data["assets"]]==["coinmarketcap:123"]
    assert "start=101" in f.call_args.args[0]
    assert "/public-api/" in f.call_args.args[0]


def test_coinbase_active_products_are_pairs_not_global_coin_count():
    response={"products":[
        {"product_id":"BTC-USD","base_currency_id":"BTC","quote_currency_id":"USD",
         "price":"80000","volume_24h":"120","trading_disabled":False,"status":"online"},
        {"product_id":"DELISTED-USD","status":"offline"},
        {"product_id":"DISABLED-USD","trading_disabled":True},
    ]}
    with patch.object(C,"_fetch",return_value=response):
        data=C.coinbase_pairs(0,100)
    assert [p["id"] for p in data["pairs"]]==["coinbase:BTC-USD"]
    assert data["pairs"][0]["base"]=="BTC"
    assert "not unique coin counts" in data["note"]


def test_publisher_rss_only_links_approved_original_hosts():
    xml=b"""<rss><channel>
      <item><title>Publisher headline</title>
        <link>https://cointelegraph.com/news/interesting-research</link>
        <pubDate>Thu, 29 Oct 2026 12:00:00 GMT</pubDate>
      </item>
      <item><title>Unapproved host</title><link>https://evil.invalid/copy</link></item>
    </channel></rss>"""
    with patch.object(C,"_fetch",return_value=xml):
        result=C.news(20)
    assert len(result["articles"])==1
    assert result["articles"][0]["source"]=="Cointelegraph"
    assert "headline" in result["articles"][0]["title"].lower()
    assert "Publisher RSS" in result["source"]


def test_expected_value_estimator_never_infers_missing_inputs():
    input_values={
        "miner_hashrate_hps":1e9,
        "network_hashrate_hps":1e12,
        "block_reward":5,
        "blocks_per_day":144,
        "price_usd":2,
        "fee_percent":2,
        "power_watts":500,
        "electricity_usd_per_kwh":.1
    }
    out=C.mining_estimate(input_values)
    assert out["coin_per_day_expected"]==pytest.approx(.7056)
    assert out["gross_usd_per_day_expected"]==pytest.approx(1.4112)
    assert out["electricity_usd_per_day"]==pytest.approx(1.2)
    assert out["net_usd_per_day_before_other_costs"]==pytest.approx(.2112)
    assert "not actual revenue" in out["note"]
    with pytest.raises(ValueError):
        C.mining_estimate({**input_values,"network_hashrate_hps":0})
    with pytest.raises(ValueError):
        C.mining_estimate({**input_values,"fee_percent":101})
    with pytest.raises(ValueError):
        C.mining_estimate({k:v for k,v in input_values.items() if k!="price_usd"})


def test_reject_invalid_catalog_search_and_poisoned_numeric_input():
    with pytest.raises(ValueError):
        C.cg_catalog_search("\\x00invalid")
    with pytest.raises(ValueError):
        C.cg_market_page(101,250)
    with pytest.raises(ValueError):
        C.coinbase_pairs(-1,100)
    assert C._numeric("Infinity") is None
