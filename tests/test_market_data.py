"""Offline deterministic tests for Silver Scan research provider adapters."""
import time
from unittest.mock import patch

import pytest

from app import market_data as m


@pytest.fixture(autouse=True)
def clear_cache():
    m._CACHE.clear()
    yield
    m._CACHE.clear()


def coin(id="bitcoin"):
    return {
        "id": id, "name": "Bitcoin", "symbol": "btc",
        "market_cap_rank": 1, "current_price": 90000.1,
        "price_change_percentage_24h": -0.3,
        "total_volume": 30000000,
        "market_cap": 120000000,
        "circulating_supply": 1000000,
    }


def test_markets_provider_id_attribution_and_cache():
    with patch.object(m, "_read_json", return_value=[coin(), coin("bitcoin-cash")]) as mocked:
        first = m.markets(1)
        second = m.markets(2)
    assert mocked.call_count == 1
    assert first["source"] == "CoinGecko"
    assert first["stale"] is False
    assert first["assets"][0]["id"] == "coingecko:bitcoin"
    assert second["assets"][1]["id"] == "coingecko:bitcoin-cash"
    assert first["assets"][0]["volume_24h_usd"] == 30000000
    assert "not native" in first["note"].lower()


def test_markets_bounds_and_missing_fields():
    for limit in (-1, 0, 101, "20"):
        with pytest.raises(ValueError):
            m.markets(limit)
    with patch.object(m, "_read_json", return_value=[{"id": "unknown", "symbol": "x", "current_price": None}]):
        data = m.markets()
    assert data["assets"][0]["price_usd"] is None


def test_stale_cache_is_explicit_then_expires():
    with patch.object(m, "_read_json", return_value=[coin()]):
        initial = m.markets()
    m._CACHE["market-cap:usd:100"] = (time.time() - 130, [coin()])
    with patch.object(m, "_read_json", side_effect=m.ProviderUnavailable()):
        stale = m.markets()
    assert stale["stale"] is True
    assert stale["fetched_at"] < initial["fetched_at"]
    m._CACHE["market-cap:usd:100"] = (time.time() - 700, [coin()])
    with patch.object(m, "_read_json", side_effect=m.ProviderUnavailable()):
        with pytest.raises(m.ProviderUnavailable):
            m.markets()


def test_dex_pair_identity_uses_chain_and_pair_address():
    def pair(chain, contract):
        return {
            "chainId": chain, "dexId": "test-dex",
            "pairAddress": contract,
            "baseToken": {"symbol": "ABC", "address": "base-address"},
            "quoteToken": {"symbol": "USD", "address": "quote-address"},
            "priceUsd": "0.15",
            "liquidity": {"usd": 200000},
            "volume": {"h24": 20000},
            "priceChange": {"h24": -2.0},
            "url": "https://dexscreener.com/" + chain + "/" + contract,
        }
    payload = {"pairs": [pair("solana", "pair123"), pair("ethereum", "pair123")]}
    with patch.object(m, "_read_json", return_value=payload):
        response = m.dex_search("ABC")
    assert response["source"] == "DEX Screener"
    assert response["pairs"][0]["id"] == "dexscreener:solana:pair123"
    assert response["pairs"][1]["id"] == "dexscreener:ethereum:pair123"
    assert response["pairs"][0]["base_token"]["address"] == "base-address"
    assert response["pairs"][0]["volume_24h_usd"] == 20000


def test_dex_query_validation_and_unavailable_states():
    for query in ("", "x", "a" * 81, "hello\nworld"):
        with pytest.raises(ValueError):
            m.dex_search(query)
    with patch.object(m, "_read_json", return_value={"pairs": []}):
        assert m.dex_search("some token")["pairs"] == []
    with patch.object(m, "_read_json", side_effect=m.ProviderUnavailable()):
        with pytest.raises(m.ProviderUnavailable):
            m.dex_search("new token")


def test_upstream_payload_must_have_expected_shape():
    with patch.object(m, "_read_json", return_value={"error": "rate limited"}):
        with pytest.raises(m.ProviderUnavailable):
            m.markets()
    with patch.object(m, "_read_json", return_value=[]):
        with pytest.raises(m.ProviderUnavailable):
            m.dex_search("token")


def test_sparkline_uses_real_provider_values_and_bounds_size():
    raw = [coin()]
    raw[0]["image"] = "https://coin-images.coingecko.com/coins/images/1/small/bitcoin.png"
    raw[0]["sparkline_in_7d"] = {"price": list(range(180))}
    raw[0]["price_change_percentage_1h_in_currency"] = 1.5
    raw[0]["price_change_percentage_7d_in_currency"] = -3.5
    with patch.object(m, "_read_json", return_value=raw):
        result = m.markets(100)["assets"][0]
    assert result["change_1h_pct"] == 1.5
    assert result["change_7d_pct"] == -3.5
    assert 2 <= len(result["sparkline_7d"]) <= 34
    assert result["icon"].startswith("https://coin-images.coingecko.com/")


def test_unsafe_coin_icons_not_returned():
    assert m._coin_image("javascript:alert(1)") is None
    assert m._coin_image("https://attacker.example/icon.png") is None
    assert m._coin_image("https://coin-images.coingecko.com.evil.example/icon.png") is None


def test_global_market_observations_and_attribution():
    upstream = {"data": {
        "total_market_cap": {"usd": 123_456_789},
        "total_volume": {"usd": 19_000_000},
        "market_cap_percentage": {"btc": 52.7, "eth": 10.2},
        "active_cryptocurrencies": 12345,
        "market_cap_change_percentage_24h_usd": -1.2,
    }}
    with patch.object(m, "_read_json", return_value=upstream):
        result = m.global_market()
    assert result["source"] == "CoinGecko"
    assert result["market_cap_usd"] == 123_456_789
    assert result["btc_dominance_pct"] == 52.7
    assert result["active_cryptocurrencies"] == 12345


def test_fear_greed_source_score_history_and_unavailable():
    # Latest observations arrive in reverse order; adapter sorts them by time.
    sample = {"data": [
        {"value": "55", "value_classification": "Neutral", "timestamp": "1700000100"},
        {"value": "28", "value_classification": "Fear", "timestamp": "1700000000"},
    ]}
    with patch.object(m, "_read_json", return_value=sample):
        result = m.market_sentiment(30)
    assert result["score"] == 55
    assert result["classification"] == "Neutral"
    assert result["source"] == "Alternative.me Crypto Fear & Greed Index"
    assert result["history"][0]["value"] == 28
    with pytest.raises(ValueError):
        m.market_sentiment(500)
    m._CACHE.clear()
    with patch.object(m, "_read_json", return_value={"data": [{"value": "150", "timestamp": "1700000100"}]}):
        with pytest.raises(m.ProviderUnavailable):
            m.market_sentiment(30)


def test_coin_profile_uses_provider_ids_contract_platforms_and_safe_links():
    raw = {
        "id": "bitcoin", "name": "Bitcoin", "symbol": "btc", "market_cap_rank": 1,
        "description": {"en": "<p>Proof of work <b>network</b></p>"},
        "market_data": {
            "current_price": {"usd": 100_000}, "market_cap": {"usd": 200_000_000},
            "total_volume": {"usd": 1_000_000}, "price_change_percentage_24h": 1.5
        },
        "platforms": {"ethereum": "0x123456", "solana": ""},
        "image": {"large": "https://coin-images.coingecko.com/coins/images/1/large/bitcoin.png"},
        "links": {"homepage": ["https://example.org"], "blockchain_site": ["https://blockchain.example"]},
    }
    with patch.object(m, "_read_json", return_value=raw):
        result = m.asset_profile("bitcoin")
    assert result["id"] == "coingecko:bitcoin"
    assert result["price_usd"] == 100_000
    assert result["description"] == "Proof of work network"
    assert result["contracts"] == [{"network": "ethereum", "contract": "0x123456"}]
    assert result["resources"][0]["label"] == "Official website"
    with pytest.raises(ValueError):
        m.asset_profile("../private")


def test_coin_chart_uses_real_timestamp_value_pairs_only():
    raw = {"prices": [[1700000000000, 10.0], [1700001000000, 11.0], [1700002000000, 10.5]]}
    with patch.object(m, "_read_json", return_value=raw):
        result = m.asset_chart("bitcoin", 7)
    assert result["days"] == 7
    assert result["source"] == "CoinGecko"
    assert len(result["points"]) == 3
    assert result["points"][0] == [1700000000000, 10]
    with pytest.raises(ValueError):
        m.asset_chart("bitcoin", 31)
