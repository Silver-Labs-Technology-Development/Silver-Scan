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

from app import main, indexer, adapters, market_data


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
