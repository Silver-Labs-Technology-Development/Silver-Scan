"""Read-only, provider-attributed market research adapters.

Silver Scan is not an exchange. CoinGecko prices and DEX Screener pairs are
external reference data, never native SilvEx executions or verified assets.
Only fixed HTTPS hosts are called. No RPC keys or provider secrets reach clients.
"""
from __future__ import annotations

import json
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MARKET_URL = "https://api.coingecko.com/api/v3/coins/markets"
DEX_URL = "https://api.dexscreener.com/latest/dex/search"
CACHE_SECONDS = 120
STALE_SECONDS = 600
MAX_BYTES = 1_000_000
_MAX_RESULTS = 100
_CACHE: dict[str, tuple[float, object]] = {}
_LOCK = threading.RLock()


class ProviderUnavailable(Exception):
    """Upstream data is not currently available and no suitable cache exists."""


def _read_json(url: str, *, key: str = ""):
    headers = {"Accept": "application/json", "User-Agent": "SilverScan/0.1 (read-only research)"}
    if key:
        headers["x-cg-demo-api-key"] = key
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=7) as response:
            if response.geturl().split("?", 1)[0] != url.split("?", 1)[0]:
                raise ProviderUnavailable("Provider redirected unexpectedly")
            content = response.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ProviderUnavailable("Provider response exceeds size limit")
            return json.loads(content)
    except (HTTPError, URLError, TimeoutError, ValueError, UnicodeDecodeError, OSError) as exc:
        raise ProviderUnavailable("External market provider temporarily unavailable") from exc


def _cached(key: str, fetch):
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] <= CACHE_SECONDS:
            return cached[1], cached[0], False
    try:
        data = fetch()
    except ProviderUnavailable:
        with _LOCK:
            cached = _CACHE.get(key)
            if cached and time.time() - cached[0] <= STALE_SECONDS:
                return cached[1], cached[0], True
        raise
    fetched = time.time()
    with _LOCK:
        _CACHE[key] = (fetched, data)
        # Bound memory even when many different DEX queries are requested.
        if len(_CACHE) > 128:
            oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
            _CACHE.pop(oldest, None)
    return data, fetched, False


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if abs(value) < 1e30 else None


def markets(limit: int = 50):
    if not isinstance(limit, int) or not 1 <= limit <= _MAX_RESULTS:
        raise ValueError("limit must be between 1 and 100")
    query = urlencode({
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": _MAX_RESULTS,
        "page": 1,
        "sparkline": "false",
    })
    raw, fetched_at, stale = _cached(
        "market-cap:usd:100",
        lambda: _read_json(MARKET_URL + "?" + query, key=os.environ.get("COINGECKO_DEMO_API_KEY", "")),
    )
    if not isinstance(raw, list):
        raise ProviderUnavailable("Market provider returned an unexpected payload")
    coins = []
    for row in raw[:limit]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        coins.append({
            "id": "coingecko:" + row["id"],  # stable provider ID, never ticker-only
            "provider_id": row["id"],
            "name": row.get("name"),
            "symbol": row.get("symbol"),
            "rank": row.get("market_cap_rank"),
            "price_usd": _number(row.get("current_price")),
            "change_24h_pct": _number(row.get("price_change_percentage_24h")),
            "market_cap_usd": _number(row.get("market_cap")),
            "volume_24h_usd": _number(row.get("total_volume")),
            "circulating_supply": _number(row.get("circulating_supply")),
            "network_identity": "provider-aggregated (not chain-verified)",
        })
    return {
        "source": "CoinGecko",
        "source_url": "https://www.coingecko.com/",
        "fetched_at": fetched_at,
        "stale": stale,
        "currency": "USD",
        "assets": coins,
        "note": "Third-party reference markets, not native Silver Labs trading volume. Assets require chain/contract verification.",
    }


def dex_search(query: str):
    query = query.strip()
    if not 2 <= len(query) <= 80 or any(ord(c) < 32 for c in query):
        raise ValueError("q must have 2–80 printable characters")
    raw, fetched_at, stale = _cached(
        "dex:" + query.lower(),
        lambda: _read_json(DEX_URL + "?" + urlencode({"q": query})),
    )
    if not isinstance(raw, dict) or not isinstance(raw.get("pairs"), list):
        raise ProviderUnavailable("DEX provider returned an unexpected payload")
    pairs = []
    for row in raw["pairs"][:25]:
        if not isinstance(row, dict):
            continue
        chain, address = row.get("chainId"), row.get("pairAddress")
        base = row.get("baseToken") if isinstance(row.get("baseToken"), dict) else {}
        quote = row.get("quoteToken") if isinstance(row.get("quoteToken"), dict) else {}
        if not isinstance(chain, str) or not isinstance(address, str) or not chain or not address:
            continue
        pairs.append({
            "id": "dexscreener:" + chain + ":" + address,
            "chain_id": chain,
            "dex_id": row.get("dexId"),
            "pair_address": address,
            "base_token": {
                "name": base.get("name"),
                "symbol": base.get("symbol"),
                "address": base.get("address"),
            },
            "quote_token": {
                "name": quote.get("name"),
                "symbol": quote.get("symbol"),
                "address": quote.get("address"),
            },
            "price_usd": row.get("priceUsd"),
            "liquidity_usd": _number((row.get("liquidity") or {}).get("usd")) if isinstance(row.get("liquidity"), dict) else None,
            "volume_24h_usd": _number((row.get("volume") or {}).get("h24")) if isinstance(row.get("volume"), dict) else None,
            "change_24h_pct": _number((row.get("priceChange") or {}).get("h24")) if isinstance(row.get("priceChange"), dict) else None,
            "source_url": row.get("url") if isinstance(row.get("url"), str) and row["url"].startswith("https://dexscreener.com/") else None,
        })
    return {
        "source": "DEX Screener",
        "source_url": "https://dexscreener.com/",
        "fetched_at": fetched_at,
        "stale": stale,
        "pairs": pairs,
        "note": "External DEX research only. Listing does not imply token verification, a Silver Labs listing or a supported swap route.",
    }
