"""Read-only, provider-attributed market research adapters.

Silver Scan is not an exchange. CoinGecko prices and DEX Screener pairs are
external reference data, never native SilvEx executions or verified assets.
Only fixed HTTPS hosts are called. No RPC keys or provider secrets reach clients.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote, urlsplit
from urllib.request import Request, urlopen

COINGECKO_API = "https://api.coingecko.com/api/v3"
MARKET_URL = COINGECKO_API + "/coins/markets"
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
        "sparkline": "true",
        "price_change_percentage": "1h,24h,7d",
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
            "change_1h_pct": _number(row.get("price_change_percentage_1h_in_currency")),
            "change_24h_pct": _number(row.get("price_change_percentage_24h_in_currency") if row.get("price_change_percentage_24h_in_currency") is not None else row.get("price_change_percentage_24h")),
            "change_7d_pct": _number(row.get("price_change_percentage_7d_in_currency")),
            "icon": _coin_image(row.get("image")),
            "sparkline_7d": _sparkline(row.get("sparkline_in_7d")),,
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


_COIN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


def _validate_coin_id(coin_id: str) -> str:
    if not isinstance(coin_id, str) or not _COIN_ID.fullmatch(coin_id):
        raise ValueError("coin ID must be a valid CoinGecko identifier")
    return coin_id


def _coin_image(value):
    """Allow only direct known image CDNs, not arbitrary remote tracking links."""
    if not isinstance(value, str) or len(value) > 500:
        return None
    p = urlsplit(value)
    if p.scheme == "https" and p.hostname in {"coin-images.coingecko.com", "assets.coingecko.com"}:
        return value
    return None


def _sparkline(raw):
    values = raw.get("price") if isinstance(raw, dict) else None
    if not isinstance(values, list):
        return []
    # Max 34 points / coin to keep network and browser work bounded.
    step = max(1, (len(values) + 33) // 34)
    points = [_number(value) for value in values[::step]][:34]
    return [value for value in points if value is not None]


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _plain_description(value):
    if not isinstance(value, str):
        return ""
    extractor = _TextExtractor()
    extractor.feed(value[:10000])
    return " ".join(" ".join(extractor.parts).split())[:1300]


def _safe_external_url(value):
    if not isinstance(value, str) or len(value) > 500:
        return None
    parsed = urlsplit(value)
    if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
        return value
    return None


def global_market():
    """Real CoinGecko global overview, never an estimate from top-100 assets."""
    raw, fetched_at, stale = _cached(
        "global:usd",
        lambda: _read_json(COINGECKO_API + "/global", key=os.environ.get("COINGECKO_DEMO_API_KEY", "")),
    )
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        raise ProviderUnavailable("Global market provider returned an unexpected payload")
    return {
        "source": "CoinGecko",
        "fetched_at": fetched_at,
        "stale": stale,
        "market_cap_usd": _number((data.get("total_market_cap") or {}).get("usd")),
        "volume_24h_usd": _number((data.get("total_volume") or {}).get("usd")),
        "btc_dominance_pct": _number((data.get("market_cap_percentage") or {}).get("btc")),
        "eth_dominance_pct": _number((data.get("market_cap_percentage") or {}).get("eth")),
        "active_cryptocurrencies": data.get("active_cryptocurrencies") if type(data.get("active_cryptocurrencies")) is int else None,
        "market_cap_change_24h_pct": _number(data.get("market_cap_change_percentage_24h_usd")),
        "note": "External market coverage, not all coins or all chains indexed by Silver Scan.",
    }


def asset_profile(coin_id: str):
    """Coin profile including verified provider ID and platform contract references."""
    coin_id = _validate_coin_id(coin_id)
    query = urlencode({
        "localization": "false", "tickers": "false", "market_data": "true",
        "community_data": "false", "developer_data": "false", "sparkline": "false",
    })
    raw, fetched_at, stale = _cached(
        "profile:" + coin_id,
        lambda: _read_json(
            COINGECKO_API + "/coins/" + quote(coin_id, safe="") + "?" + query,
            key=os.environ.get("COINGECKO_DEMO_API_KEY", ""),
        ),
    )
    if not isinstance(raw, dict) or raw.get("id") != coin_id:
        raise ProviderUnavailable("Coin profile provider returned an unexpected payload")
    m = raw.get("market_data") if isinstance(raw.get("market_data"), dict) else {}
    def usd(key):
        value = m.get(key)
        return _number(value.get("usd")) if isinstance(value, dict) else None
    platforms = raw.get("platforms") if isinstance(raw.get("platforms"), dict) else {}
    contracts = [
        {"network": chain, "contract": address}
        for chain, address in list(platforms.items())[:40]
        if isinstance(chain, str) and isinstance(address, str) and address.strip()
    ]
    links = raw.get("links") if isinstance(raw.get("links"), dict) else {}
    resources = []
    for label, values in [
        ("Official website", links.get("homepage")),
        ("Blockchain explorer", links.get("blockchain_site")),
        ("Source code", links.get("repos_url", {}).get("github") if isinstance(links.get("repos_url"), dict) else []),
    ]:
        if not isinstance(values, list):
            continue
        safe = next((_safe_external_url(value) for value in values if _safe_external_url(value)), None)
        if safe:
            resources.append({"label": label, "url": safe})
    return {
        "source": "CoinGecko", "fetched_at": fetched_at, "stale": stale,
        "id": "coingecko:" + coin_id, "provider_id": coin_id,
        "name": raw.get("name"), "symbol": raw.get("symbol"), "rank": raw.get("market_cap_rank"),
        "icon": _coin_image(raw.get("image", {}).get("large") if isinstance(raw.get("image"), dict) else None),
        "description": _plain_description((raw.get("description") or {}).get("en") if isinstance(raw.get("description"), dict) else None),
        "categories": [item for item in (raw.get("categories") or [])[:12] if isinstance(item, str)],
        "price_usd": usd("current_price"), "market_cap_usd": usd("market_cap"),
        "volume_24h_usd": usd("total_volume"), "ath_usd": usd("ath"),
        "atl_usd": usd("atl"), "high_24h_usd": usd("high_24h"), "low_24h_usd": usd("low_24h"),
        "fdv_usd": usd("fully_diluted_valuation"),
        "change_24h_pct": _number(m.get("price_change_percentage_24h")),
        "change_7d_pct": _number(m.get("price_change_percentage_7d")),
        "circulating_supply": _number(m.get("circulating_supply")),
        "total_supply": _number(m.get("total_supply")),
        "max_supply": _number(m.get("max_supply")),
        "contracts": contracts,
        "resources": resources,
        "note": "CoinGecko aggregates markets. Listing does not verify a coin or contract, and does not indicate trading availability on SilvEx.",
    }


def asset_chart(coin_id: str, days: int):
    coin_id = _validate_coin_id(coin_id)
    if type(days) is not int or days not in (1, 7, 30, 90, 365):
        raise ValueError("days must be one of 1, 7, 30, 90, 365")
    query = urlencode({"vs_currency": "usd", "days": days})
    raw, fetched_at, stale = _cached(
        "chart:" + coin_id + ":" + str(days),
        lambda: _read_json(
            COINGECKO_API + "/coins/" + quote(coin_id, safe="") + "/market_chart?" + query,
            key=os.environ.get("COINGECKO_DEMO_API_KEY", ""),
        ),
    )
    raw_points = raw.get("prices") if isinstance(raw, dict) else None
    if not isinstance(raw_points, list):
        raise ProviderUnavailable("Price history not available from source")
    step = max(1, (len(raw_points) + 249) // 250)
    points = [
        [int(point[0]), float(point[1])]
        for point in raw_points[::step]
        if isinstance(point, list) and len(point) == 2
        and type(point[0]) in (int, float) and _number(point[1]) is not None
    ][:250]
    return {
        "source": "CoinGecko", "fetched_at": fetched_at, "stale": stale,
        "provider_id": coin_id, "days": days, "currency": "USD", "points": points,
    }


def market_sentiment(limit: int = 30):
    """Alternative.me Fear & Greed: independently sourced, not a CMC score.

    Attribution must be shown directly alongside the score and graph. Returns
    an unavailable response through the API when source data cannot be read.
    """
    if type(limit) is not int or limit not in (7, 30, 90):
        raise ValueError("sentiment history is limited to 7, 30 or 90 days")
    url = "https://api.alternative.me/fng/?" + urlencode({"limit": limit})
    raw, fetched_at, stale = _cached(
        "fear-greed:" + str(limit),
        lambda: _read_json(url),
    )
    rows = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ProviderUnavailable("Fear and Greed provider returned no observations")
    history = []
    allowed = {"Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"}
    for item in rows[:limit]:
        if not isinstance(item, dict):
            continue
        try:
            score = int(item.get("value"))
            timestamp = int(item.get("timestamp"))
        except (ValueError, TypeError):
            continue
        if not 0 <= score <= 100 or timestamp <= 0:
            continue
        cls = item.get("value_classification")
        history.append({
            "value": score,
            "classification": cls if cls in allowed else "Unclassified",
            "timestamp": timestamp,
        })
    if not history:
        raise ProviderUnavailable("Fear and Greed observations are invalid")
    history.sort(key=lambda item: item["timestamp"])
    latest = history[-1]
    return {
        "source": "Alternative.me Crypto Fear & Greed Index",
        "source_url": "https://alternative.me/crypto/fear-and-greed-index/",
        "fetched_at": fetched_at,
        "stale": stale,
        "score": latest["value"],
        "classification": latest["classification"],
        "observation_timestamp": latest["timestamp"],
        "history": history,
        "note": "Market sentiment indicator, not coin-specific sentiment, investment advice, or a CoinMarketCap proprietary score.",
    }
