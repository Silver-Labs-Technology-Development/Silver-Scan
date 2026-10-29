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
