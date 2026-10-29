"""Optional LiveCoinWatch market data adapter.

Docs: https://livecoinwatch.github.io/lcw-api-docs/
LiveCoinWatch uses an authenticated POST /coins/list endpoint, 100 records
maximum per request. API key stays server-side and is never returned.
Its provider "code" must not be presumed equivalent to a CoinGecko ID or
CoinMarketCap ID. Source license/attribution must be respected.
"""
from __future__ import annotations
import json
import math
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from app.market_data import ProviderUnavailable

_HOST = "api.livecoinwatch.com"
_ENDPOINT = "https://api.livecoinwatch.com/coins/list"
_CACHE = {}
_LOCK = threading.RLock()
_CODE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")
_MAX_BODY = 1_500_000


def _number(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        result = float(value)
        return result if math.isfinite(result) and abs(result) < 1e30 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _post(offset, limit, key):
    payload = json.dumps({"currency":"USD", "sort":"rank",
                          "order":"ascending", "offset":offset,
                          "limit":limit, "meta":True}).encode("utf-8")
    request = Request(_ENDPOINT,data=payload,method="POST",headers={
        "Content-Type":"application/json","Accept":"application/json",
        "X-API-KEY":key,"User-Agent":"SilverScan/0.4 (research; attributed)"
    })
    try:
        with urlopen(request,timeout=8) as response:
            if (urlsplit(response.geturl()).hostname != _HOST or
                    urlsplit(response.geturl()).scheme != "https"):
                raise ProviderUnavailable("Provider redirect not allowed")
            body=response.read(_MAX_BODY+1)
        if len(body)>_MAX_BODY:
            raise ProviderUnavailable("Provider response too large")
        parsed=json.loads(body)
        if not isinstance(parsed,list):
            raise ProviderUnavailable("Invalid LiveCoinWatch response")
        return parsed
    except (HTTPError,URLError,TimeoutError,ValueError,OSError,UnicodeDecodeError) as exc:
        raise ProviderUnavailable("LiveCoinWatch data unavailable") from exc


def market_page(page=1,limit=50):
    if type(page) is not int or not 1<=page<=500:
        raise ValueError("page must be 1–500")
    if type(limit) is not int or limit not in (25,50,100,200):
        raise ValueError("page size must be 25, 50, 100 or 200")
    key=os.environ.get("LIVECOINWATCH_API_KEY","").strip()
    if not key:
        raise ProviderUnavailable("LiveCoinWatch API key not configured")
    cachekey=(page,limit)
    with _LOCK:
        saved=_CACHE.get(cachekey)
        if saved and time.monotonic()-saved[0]<240:
            return dict(saved[1],stale=False)
    raw=[]
    try:
        offset=(page-1)*limit
        for batch in range(0,limit,100):
            count=min(100,limit-batch)
            segment=_post(offset+batch,count,key)
            raw.extend(segment)
            if len(segment)<count:break
    except ProviderUnavailable:
        with _LOCK:
            old=_CACHE.get(cachekey)
            if old and time.monotonic()-old[0]<=1200:
                return dict(old[1],stale=True)
        raise
    assets=[]
    for item in raw:
        if not isinstance(item,dict):
            continue
        code=item.get("code")
        if not isinstance(code,str) or not _CODE.fullmatch(code):
            continue
        price=_number(item.get("rate"))
        vol=_number(item.get("volume"))
        if price is None or price<=0 or vol is None or vol<=0:
            continue
        delta=item.get("delta") if isinstance(item.get("delta"),dict) else {}
        def change(k):
            ratio=_number(delta.get(k))
            return (ratio-1)*100 if ratio is not None else None
        rank=item.get("rank")
        rank=rank if type(rank) is int and rank>=1 else None
        assets.append({
            "id":"livecoinwatch:"+code,"provider_id":code,
            "name":str(item.get("name") or code)[:120],
            "symbol":str(item.get("symbol") or code)[:30],
            "rank":rank,"price_usd":price,
            "volume_24h_usd":vol,
            "market_cap_usd":_number(item.get("cap")),
            "circulating_supply":_number(item.get("circulatingSupply")),
            "change_1h_pct":change("hour"),"change_24h_pct":change("day"),
            "change_7d_pct":change("week"),
            "icon":None,"sparkline_7d":None,
            "market_status":"provider-reported-volume",
        })
    timestamp=int(time.time())
    result={"source":"LiveCoinWatch /coins/list","page":page,
            "limit":limit,"provider_rows":len(raw),
            "has_more":len(raw)==limit,"assets":assets,
            "fetched_at":timestamp,"stale":False,
            "note":"LiveCoinWatch API rankings, distinct from CoinGecko and CoinMarketCap IDs. "
                   "Delta ratios converted to percentage changes. Public display requires legible "
                   "LiveCoinWatch attribution on this page. A provider snapshot is not independently indexed coverage."}
    with _LOCK:
        _CACHE[cachekey]=(time.monotonic(),result)
        if len(_CACHE)>32:
            _CACHE.pop(next(iter(_CACHE)),None)
    return result


def last_observation():
    with _LOCK:
        return max((entry[1]["fetched_at"] for entry in _CACHE.values()),default=None)
