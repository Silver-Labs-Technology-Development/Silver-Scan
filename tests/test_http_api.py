"""Real loopback HTTP transport tests with stubbed BTC RPC/provider data.

Runs entirely offline, using an ephemeral local port. Does not mine, write
blocks, submit transactions, or call a remote API.
"""
from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

import pytest

from app import main, indexer, adapters, market_data, coverage


@pytest.fixture
def api_server(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "DB_PATH", str(tmp_path / "test-index.sqlite3"))
    indexer.init_db()
    monkeypatch.setattr(adapters, "btcs_health", lambda: {
        "chain": "regtest", "blocks": 2, "bestBlockHash": "a" * 64,
        "verificationProgress": 1.0, "pruned": False,
    })
    monkeypatch.setattr(adapters, "btcs_recent_blocks", lambda n: [
        {"hash": "a" * 64, "height": 2, "txCount": 1, "time": 1700000000}
    ][:n])
    monkeypatch.setattr(adapters, "btcs_block", lambda ident: {
        "height": int(ident) if str(ident).isdigit() else 2,
        "hash": "a" * 64, "txCount": 0, "time": 1700000000, "txids": [],
    })
    monkeypatch.setattr(adapters, "btcs_tx", lambda txid: {
        "txid": txid, "vin": [], "vout": [], "size": 200, "confirmations": 1,
    })
    monkeypatch.setattr(adapters.rpc, "call", lambda url, user, password, method, params=None: (
        {"isvalid": True} if method == "validateaddress" else None
    ))
    monkeypatch.setattr(market_data, "markets", lambda limit=50: {
        "source": "CoinGecko", "assets": [], "stale": False, "fetched_at": 1234,
    })
    monkeypatch.setattr(market_data, "global_market", lambda: {
        "source": "CoinGecko", "market_cap_usd": 123000,
        "btc_dominance_pct": 50.0, "fetched_at": 1234,
    })
    monkeypatch.setattr(market_data, "market_sentiment", lambda days=30: {
        "source": "Alternative.me Crypto Fear & Greed Index",
        "score": 42, "classification": "Fear", "history": [],
        "fetched_at": 1234,
    })
    monkeypatch.setattr(market_data, "asset_profile", lambda coin_id: {
        "source": "CoinGecko", "provider_id": coin_id, "id": "coingecko:" + coin_id,
    })
    monkeypatch.setattr(market_data, "asset_chart", lambda coin_id, days: {
        "source": "CoinGecko", "provider_id": coin_id, "days": days,
        "points": [[1700000000000, 1.0], [1700000001000, 1.1]],
    })
    monkeypatch.setattr(coverage, "cg_catalog_search", lambda q, limit: {
        "source": "CoinGecko /coins/list", "catalog_count": 20001,
        "matches": [{"id": "coingecko:bitcoin-silver-2", "name": "Bitcoin Silver"}],
    })
    monkeypatch.setattr(coverage, "cg_market_page", lambda page, limit: {
        "source": "CoinGecko", "page": page, "limit": limit, "assets": [],
    })
    monkeypatch.setattr(coverage, "cg_quote", lambda coin: {
        "source": "CoinGecko", "asset": {"id": "coingecko:" + coin},
    })
    monkeypatch.setattr(coverage, "cmc_active", lambda page, limit: {
        "source": "CoinMarketCap", "page": page, "assets": [],
    })
    monkeypatch.setattr(coverage, "coinbase_pairs", lambda offset, limit: {
        "source": "Coinbase Advanced Trade", "offset": offset, "pairs": [],
    })
    monkeypatch.setattr(coverage, "news", lambda limit: {
        "source": "Publisher RSS feeds", "articles": [],
    })
    monkeypatch.setattr(market_data, "dex_search", lambda query: {
        "source": "DEX Screener", "pairs": [], "stale": False, "fetched_at": 1234,
    })
    server = ThreadingHTTPServer(("127.0.0.1", 0), main.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request(base, path, method="GET"):
    req = Request(base + path, method=method)
    try:
        with urlopen(req, timeout=3) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def data(base, path, method="GET"):
    status, headers, body = request(base, path, method)
    return status, headers, json.loads(body)


def test_static_assets_are_served_and_safe(api_server):
    for path, ctype in [
        ("/", "text/html"),
        ("/styles.css", "text/css"),
        ("/explorer.js", "application/javascript"),
        ("/research.js", "application/javascript"),
        ("/charts.js", "application/javascript"),
        ("/features.html", "text/html"),
        ("/features.css", "text/css"),
        ("/features.js", "application/javascript"),
        ("/data-hub.html", "text/html"),
        ("/data-hub.css", "text/css"),
        ("/data-hub.js", "application/javascript"),
        ("/coin-watch.html", "text/html"),
        ("/news.html", "text/html"),
        ("/mining.html", "text/html"),
        ("/theme.css", "text/css"),
        ("/theme.js", "application/javascript"),
    ]:
        status, headers, body = request(api_server, path)
        assert status == 200
        assert ctype in headers["Content-Type"]
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Cache-Control"] == "no-store"
        assert len(body) > 20
    _, headers, page = request(api_server, "/")
    assert b"explorer.js" in page
    assert b"research.js" in page
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert "coin-images.coingecko.com" in headers["Content-Security-Policy"]


def test_index_writes_are_not_exposed_over_http(api_server):
    for method in ["GET", "POST"]:
        status, _, body = data(api_server, "/api/index/sync", method)
        assert status == 405
        assert "disabled" in body["error"] or "read-only" in body["error"]
    assert indexer.get_tip() == -1


def test_explorer_network_blocks_and_freshness(api_server):
    status, _, networks = data(api_server, "/api/networks")
    assert status == 200
    assert any(n["family"] == "utxo" for n in networks)
    status, _, health = data(api_server, "/api/health")
    assert status == 200 and health["chain"] == "regtest"
    status, _, blocks = data(api_server, "/api/blocks/recent?limit=10")
    assert status == 200 and len(blocks) == 1
    status, _, idx = data(api_server, "/api/index/status")
    assert status == 200 and idx["tip"] == -1
    assert idx["caught_up"] is False
    assert "db" not in idx
    status, _, result = data(api_server, "/api/search?q=2")
    assert status == 200 and result["type"] == "block"


def test_address_view_is_partial_and_paginated(api_server):
    address = "a" * 34
    status, _, result = data(api_server, f"/api/address/{address}?limit=10&offset=0")
    assert status == 200
    assert result["balance_sats"] == 0
    assert result["indexComplete"] is False
    assert result["offset"] == 0
    status, _, _ = data(api_server, "/api/address/invalid!")
    assert status == 400


def test_bad_inputs_never_leak_backend_data(api_server):
    for path in [
        "/api/blocks/recent?limit=999999",
        "/api/address/b?offset=100001",
        "/api/tx/NOT-A-HASH",
        "/api/health?network=unknown",
        "/api/blocks/recent?network=evm-demo",
        "/api/search?q=%3Cscript%3E",
    ]:
        status, _, result = data(api_server, path)
        assert status == 400
        assert isinstance(result.get("error"), str)
    status, _, unknown = data(api_server, "/api/not-a-route")
    assert status == 404 and unknown["error"] == "Not found"


def test_markets_and_dex_routes(api_server):
    status, _, markets = data(api_server, "/api/markets?limit=25")
    assert status == 200 and markets["source"] == "CoinGecko"
    status, _, dex = data(api_server, "/api/dex/search?q=bitcoin")
    assert status == 200 and dex["source"] == "DEX Screener"



def test_charts_sentiment_and_asset_profiles_use_source_backed_routes(api_server):
    status, _, global_info = data(api_server, "/api/market/global")
    assert status == 200 and global_info["source"] == "CoinGecko"
    status, _, sentiment = data(api_server, "/api/market/sentiment?days=30")
    assert status == 200 and sentiment["score"] == 42
    assert "Alternative.me" in sentiment["source"]
    status, _, profile = data(api_server, "/api/assets/profile?id=bitcoin")
    assert status == 200 and profile["provider_id"] == "bitcoin"
    status, _, chart = data(api_server, "/api/assets/chart?id=bitcoin&days=7")
    assert status == 200 and len(chart["points"]) == 2
    for path in [
        "/api/market/sentiment?days=not-a-number",
        "/api/assets/chart?id=bitcoin&days=900",
    ]:
        status, _, result = data(api_server, path)
        assert status == 400 and "error" in result



def test_source_coverage_low_rank_btcs_news_and_mining_routes(api_server):
    status, _, search = data(api_server, "/api/catalog/search?q=BTCS&limit=20")
    assert status == 200 and search["matches"][0]["id"] == "coingecko:bitcoin-silver-2"
    status, _, quote = data(api_server, "/api/asset/quote?id=bitcoin-silver-2")
    assert status == 200 and quote["asset"]["id"] == "coingecko:bitcoin-silver-2"
    status, _, market = data(api_server, "/api/catalog/page?page=2&limit=100")
    assert status == 200 and market["page"] == 2
    status, _, cmc = data(api_server, "/api/coinmarketcap/active?page=2&limit=100")
    assert status == 200 and cmc["source"] == "CoinMarketCap"
    status, _, pairs = data(api_server, "/api/coinbase/pairs?offset=100&limit=100")
    assert status == 200 and pairs["source"] == "Coinbase Advanced Trade"
    status, _, news = data(api_server, "/api/news?limit=15")
    assert status == 200 and news["source"] == "Publisher RSS feeds"
    values = {
        "miner_hashrate_hps": 1e9, "network_hashrate_hps": 1e12,
        "block_reward": 5, "blocks_per_day": 144, "price_usd": 2,
        "fee_percent": 2, "power_watts": 500, "electricity_usd_per_kwh": .10,
    }
    from urllib.parse import urlencode
    status, _, calc = data(api_server, "/api/mining/estimate?" + urlencode(values))
    assert status == 200 and calc["electricity_usd_per_day"] == pytest.approx(1.2)
    status, _, invalid = data(api_server, "/api/mining/estimate?miner_hashrate_hps=x")
    assert status == 400 and "error" in invalid


def test_silverscan_market_page_sizes_watch_quotes_and_pool_registry(api_server):
    for limit in (25, 50, 100, 200):
        status, _, market = data(api_server, f"/api/catalog/page?page=2&limit={limit}")
        assert status == 200
        assert market["page"] == 2
        assert market["limit"] == limit
    status, _, bad = data(api_server, "/api/catalog/page?page=1&limit=251")
    assert status == 400 and "error" in bad

    # No public pool is implied by a disabled staging profile.
    status, _, pool = data(api_server, "/api/mining/coins")
    assert status == 200
    assert pool["active_public_pool_coins"] == 0
    assert pool["ready_for_real_payouts"] is False
    assert [c["id"] for c in pool["coins"]] == ["btcs", "btc", "bch", "ltc", "doge"]
    assert all(c["payouts_enabled"] is False for c in pool["coins"])
    assert all(c["network_hashrate_hps"] is None for c in pool["coins"])

    # Quotes preserve the unique CoinGecko ID, not ambiguous ticker symbols.
    status, _, watch = data(api_server, "/api/coin-watch/quotes?ids=bitcoin-silver-2")
    assert status == 200
    assert watch["source"] == "CoinGecko"
    status, _, missing = data(api_server, "/api/coin-watch/quotes?ids=")
    assert status == 400 and "error" in missing
    status, _, too_many = data(api_server, "/api/coin-watch/quotes?ids=" + ",".join(["bitcoin"] * 51))
    assert status == 400 and "error" in too_many
