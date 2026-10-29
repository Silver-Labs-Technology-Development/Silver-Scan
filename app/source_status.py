"""Explain provider coverage without claiming an unverified unified asset count."""
import os
import time

from app import coverage as C
from app import livecoinwatch as L
from app import pool_market as P


def _cache_last(prefixes):
    with C._LOCK:
        timestamps=[entry[2] for key,entry in C._CACHE.items()
                    if any(key.startswith(prefix) for prefix in prefixes)
                    and isinstance(entry,tuple) and len(entry)>2]
    return max(timestamps,default=None)


def _source(name,feature,access,observed_at=None,link=None):
    now=int(time.time())
    if observed_at:
        status="observed_recently" if now-observed_at<=3600 else "observed_earlier"
    else:
        status=access
    return {"name":name,"feature":feature,"access":access,
            "status":status,"last_observed":observed_at,
            "docs_url":link}


def providers():
    mps,_warning=P._snapshot()
    last_mps=mps.get("fetched_at") if mps and type(mps.get("fetched_at")) is int else None
    rows=[
        _source("CoinGecko","Coin IDs, market listings, prices, global metrics, categories",
                "requestable",_cache_last(("cg:","coingecko:")),
                "https://www.coingecko.com/en/api"),
        _source("CoinMarketCap","Market listings, exchange IDs, global market references",
                "requestable",_cache_last(("cmc:",)),
                "https://coinmarketcap.com/api/"),
        _source("Coinbase","Available Coinbase trading pairs (not unique global coins)",
                "requestable",_cache_last(("coinbase:",)),
                "https://www.coinbase.com/"),
        _source("LiveCoinWatch","Ranked markets and observed prices; server-side API key required",
                "requestable" if os.environ.get("LIVECOINWATCH_API_KEY","").strip() else "api_key_required",
                L.last_observation(),
                "https://www.livecoinwatch.com/tools/api"),
        _source("MiningPoolStats","Pool and network comparisons; only approved operator dataset",
                "operator_import_configured" if mps else "permissioned_import_required",
                last_mps if mps else None,
                "https://miningpoolstats.stream/bitcoinsilver"),
    ]
    return {
        "sources":rows,
        "provider_count":len(rows),
        "verified_unique_coin_count":None,
        "asset_identity_merge_active":False,
        "fetched_at":int(time.time()),
        "note":"Provider counts overlap. Source status shows observed local requests, not a live connection test. "
               "No 22k+ unique trading coin claim until chain/network/contract-aware entity matching, "
               "licensed ingestion and an audited active-market count exist. "
               "Coinbase counts pairs; MiningPoolStats counts mining pools, not crypto assets.",
    }
