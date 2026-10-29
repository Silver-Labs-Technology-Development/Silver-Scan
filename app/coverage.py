"""Independent read-only provider adapters and broad active asset discovery.

- CoinGecko: /coins/list ID catalog, /search, active /coins/markets quotes.
- CoinMarketCap: keyless public active listings when available; optional private key.
- Coinbase: public spot trading pairs, which are NOT coin market caps.
- News: publisher RSS headlines/links with attribution, no full article copying.
- Mining: inputs-only profitability estimates, never implied actual revenue.

No live provider count or quote is represented as a deployed Silver Scan index.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from html import unescape
import json
import math
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from app import market_data as M

CG="https://api.coingecko.com/api/v3"
CMC="https://pro-api.coinmarketcap.com"
COINBASE="https://api.coinbase.com/api/v3/brokerage/market/products"
FEEDS={
    "CoinDesk": ("https://www.coindesk.com/arc/outboundfeeds/rss/", "coindesk.com"),
    "Cointelegraph": ("https://cointelegraph.com/rss", "cointelegraph.com"),
    "Decrypt": ("https://decrypt.co/feed", "decrypt.co"),
    "The Block": ("https://www.theblock.co/rss.xml", "theblock.co"),
    "Bitcoin Magazine": ("https://bitcoinmagazine.com/feed", "bitcoinmagazine.com"),
}
_ALLOWED={"api.coingecko.com","pro-api.coinmarketcap.com","api.coinbase.com",
          "www.coindesk.com","cointelegraph.com","decrypt.co",
          "www.theblock.co","bitcoinmagazine.com"}
_LOCK=threading.RLock()
_CACHE={}
_SIZES={"json":4_000_000,"xml":600_000}
_ID=re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
_CMC_API_KEY=os.getenv("CMC_API_KEY", "").strip()

# Favicons are requested directly from the publisher's public website; no
# tracking proxy or third-party favicon API. Bad/missing images use text fallback.
PUBLISHER_FAVICONS = {
    "CoinDesk": "https://www.coindesk.com/favicon.ico",
    "Cointelegraph": "https://cointelegraph.com/favicon.ico",
    "Decrypt": "https://decrypt.co/favicon.ico",
    "The Block": "https://www.theblock.co/favicon.ico",
    "Bitcoin Magazine": "https://bitcoinmagazine.com/favicon.ico",
}
_IMAGE_DOMAINS = {
    "CoinDesk": ("coindesk.com", "coindeskcdn.com", "cdn.sanity.io"),
    "Cointelegraph": ("cointelegraph.com",),
    "Decrypt": ("decrypt.co",),
    "The Block": ("theblock.co",),
    "Bitcoin Magazine": ("bitcoinmagazine.com", "btcinc.com"),
}
_MEDIA = "{http://search.yahoo.com/mrss/}"
_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"

def _news_image(url, publisher):
    """Only return publisher/CDN-owned HTTPS article thumbnails from feed data."""
    if not isinstance(url, str) or len(url)>1200:
        return None
    candidate=unescape(url.strip())
    try:
        parts=urlsplit(candidate)
        hostname=parts.hostname
        if (parts.scheme != "https" or not hostname or parts.username or
                parts.password or parts.port not in (None,443)):
            return None
    except ValueError:
        return None
    if hostname not in _IMAGE_DOMAINS.get(publisher,()):
        suffixes=_IMAGE_DOMAINS.get(publisher,())
        if not any(hostname.endswith("."+suffix) for suffix in suffixes):
            return None
    if not parts.path or parts.path=="/":
        return None
    return candidate

class _FirstImage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.source=None
    def handle_starttag(self,tag,attrs):
        if self.source is None and tag.lower()=="img":
            attrs=dict(attrs)
            self.source=attrs.get("src") or attrs.get("data-src")

def _rss_image(item,publisher):
    """RSS media:thumbnail, media:content, enclosure, description image."""
    for tag in (_MEDIA+"thumbnail",_MEDIA+"content","enclosure"):
        for node in item.findall(tag):
            url=_news_image(node.get("url"),publisher)
            if url:return url
    for tag in ("description",_CONTENT+"encoded"):
        raw=item.findtext(tag)
        if raw:
            parser=_FirstImage()
            try:parser.feed(raw[:20000])
            except ValueError:continue
            valid=_news_image(parser.source,publisher)
            if valid:return valid
    return None



def _fetch(url, *, headers=None, kind="json"):
    hostname=urlsplit(url).hostname
    if hostname not in _ALLOWED or urlsplit(url).scheme!="https":
        raise ValueError("Disallowed provider host")
    req=Request(url, headers={"User-Agent":"SilverScan/0.3 (+read-only research)",
                              "Accept":"application/json" if kind=="json" else "application/rss+xml, application/xml",
                              **(headers or {})})
    try:
        with urlopen(req,timeout=7) as response:
            # Do not allow external redirects, including redirects to other allowed hosts.
            if urlsplit(response.geturl()).hostname!=hostname:
                raise M.ProviderUnavailable("Provider redirected to another host")
            data=response.read(_SIZES[kind]+1)
        if len(data)>_SIZES[kind]:
            raise M.ProviderUnavailable("Provider response exceeds byte limit")
        return json.loads(data) if kind=="json" else data
    except (HTTPError,URLError,TimeoutError,ValueError,UnicodeDecodeError,OSError) as exc:
        raise M.ProviderUnavailable("Data provider unavailable") from exc


def _memo(key,fn,ttl=600,stale=1800):
    now=time.monotonic()
    with _LOCK:
        cached=_CACHE.get(key)
        if cached and now-cached[0]<=ttl:
            return cached[1],cached[2],False
    try:
        value=fn()
    except M.ProviderUnavailable:
        with _LOCK:
            cached=_CACHE.get(key)
            if cached and time.monotonic()-cached[0]<=stale:
                return cached[1],cached[2],True
        raise
    with _LOCK:
        _CACHE[key]=(time.monotonic(),value,int(time.time()))
        if len(_CACHE)>96:
            old=min(_CACHE,key=lambda x:_CACHE[x][0])
            _CACHE.pop(old,None)
    return value,int(time.time()),False


def _numeric(v):
    try:
        if isinstance(v,bool) or v is None:
            return None
        f=float(v)
        return f if math.isfinite(f) and abs(f)<1e30 else None
    except (TypeError,ValueError,OverflowError):
        return None


def cg_catalog_search(query,limit=20):
    """Find symbols and low-ranked coins across provider catalog, not top-100."""
    q=query.strip().lower() if isinstance(query,str) else ""
    if not 2<=len(q)<=70 or any(ord(x)<32 for x in q):
        raise ValueError("q requires 2–70 printable characters")
    if type(limit) is not int or not 1<=limit<=40:
        raise ValueError("limit must be between 1 and 40")
    # The full catalog is a lightweight map, NOT evidence of active trading.
    try:
        raw,ts,stale=_memo("coingecko:id-map",lambda:_fetch(CG+"/coins/list?include_platform=false"),43200,86400)
        if not isinstance(raw,list):raise M.ProviderUnavailable("Invalid ID map")
        found=[]
        for item in raw:
            if not isinstance(item,dict):continue
            ident,name,symbol=item.get("id"),item.get("name"),item.get("symbol")
            if not all(isinstance(x,str) for x in (ident,name,symbol)) or not _ID.fullmatch(ident):continue
            if q in name.lower() or q in symbol.lower() or q in ident.lower():
                found.append({"id":"coingecko:"+ident,"provider_id":ident,"name":name[:120],
                              "symbol":symbol[:30],"source":"CoinGecko","market_status":"unverified"})
        found.sort(key=lambda v:(v["symbol"].lower()!=q,v["name"].lower()!=q,
                                  v["provider_id"]!="bitcoin-silver-2" if q in ("btcs","bitcoin silver") else False,
                                  not v["name"].lower().startswith(q),v["name"].lower()))
        return {"source":"CoinGecko /coins/list","catalog_count":len(raw),"matches":found[:limit],
                "fetched_at":ts,"stale":stale,
                "note":"Catalog only: IDs do not prove a coin has current trading, an active market, or a verified contract."}
    except M.ProviderUnavailable:
        # Search fallback may be rate-limited; never invent a catalog count.
        def find():
            data=_fetch(CG+"/search?"+urlencode({"query":q}))
            if not isinstance(data,dict) or not isinstance(data.get("coins"),list):raise M.ProviderUnavailable("Invalid search")
            return data
        raw,ts,stale=_memo("cg:search:"+q,find,600,1800)
        matches=[]
        for item in raw["coins"]:
            if isinstance(item,dict) and isinstance(item.get("id"),str) and _ID.fullmatch(item["id"]):
                matches.append({"id":"coingecko:"+item["id"],"provider_id":item["id"],
                                "name":item.get("name"),"symbol":item.get("symbol"),"source":"CoinGecko",
                                "market_status":"unverified"})
        return {"source":"CoinGecko /search","catalog_count":None,"matches":matches[:limit],
                "fetched_at":ts,"stale":stale,
                "note":"Provider search fallback; results have not been verified for trading activity."}


def cg_market_page(page=1,limit=100):
    if type(page) is not int or not 1<=page<=500:
        raise ValueError("page must be 1–500")
    if type(limit) is not int or not 1<=limit<=250:
        raise ValueError("limit must be 1–250")
    params=urlencode({"vs_currency":"usd","order":"market_cap_desc",
                      "per_page":limit,"page":page,"sparkline":"true" if limit<=100 else "false",
                      "price_change_percentage":"1h,24h,7d"})
    def load():
        data=_fetch(CG+"/coins/markets?"+params,
                    headers={"x-cg-demo-api-key":os.getenv("COINGECKO_DEMO_API_KEY","")} if os.getenv("COINGECKO_DEMO_API_KEY") else {})
        if not isinstance(data,list):raise M.ProviderUnavailable("Market page unavailable")
        return data
    raw,ts,stale=_memo(f"cg:page:{page}:{limit}",load,180,900)
    values=[]
    for item in raw:
        if not isinstance(item,dict) or not isinstance(item.get("id"),str):continue
        price=_numeric(item.get("current_price"));volume=_numeric(item.get("total_volume"))
        if price is None or price<=0 or volume is None or volume<=0:continue
        values.append({"id":"coingecko:"+item["id"],"provider_id":item["id"],
                       "name":item.get("name"),"symbol":item.get("symbol"),"rank":item.get("market_cap_rank"),
                       "price_usd":price,"volume_24h_usd":volume,
                       "market_cap_usd":_numeric(item.get("market_cap")),
                       "change_1h_pct":_numeric(item.get("price_change_percentage_1h_in_currency")),
                       "change_24h_pct":_numeric(item.get("price_change_percentage_24h_in_currency") if item.get("price_change_percentage_24h_in_currency") is not None else item.get("price_change_percentage_24h")),
                       "change_7d_pct":_numeric(item.get("price_change_percentage_7d_in_currency")),
                       "circulating_supply":_numeric(item.get("circulating_supply")),
                       "icon":M._coin_image(item.get("image")),
                       "sparkline_7d":M._sparkline(item.get("sparkline_in_7d")),
                       "source":"CoinGecko","market_status":"provider-reported-volume"})
    return {"source":"CoinGecko","page":page,"limit":limit,"assets":values,
            "provider_rows":len(raw),"has_more":len(raw)==limit,
            "fetched_at":ts,"stale":stale,
            "note":"Market-cap ranked provider page (not the complete coin catalog). Only rows with positive observed price and 24h volume are shown; rankings may have gaps. Page 200 omits mini-sparklines to limit upstream API payload."}


def cg_quote(coin_id):
    if not isinstance(coin_id,str) or not _ID.fullmatch(coin_id):raise ValueError("Invalid CoinGecko ID")
    data=cg_market_by_ids([coin_id])
    return {**data,"asset":data["assets"][0] if data["assets"] else None}


def cg_market_by_ids(ids):
    if not isinstance(ids,list) or len(ids)>50 or not ids or any(not isinstance(x,str) or not _ID.fullmatch(x) for x in ids):
        raise ValueError("Coin IDs must be 1–50 valid provider IDs")
    # Low-rank assets can be queried by ID directly, regardless of rank.
    params=urlencode({"vs_currency":"usd","ids":",".join(ids),"order":"market_cap_desc",
                      "per_page":len(ids),"page":1,"sparkline":"false"})
    def load():
        data=_fetch(CG+"/coins/markets?"+params,headers={"x-cg-demo-api-key":os.getenv("COINGECKO_DEMO_API_KEY","")} if os.getenv("COINGECKO_DEMO_API_KEY") else {})
        if not isinstance(data,list):raise M.ProviderUnavailable("Invalid coin quote")
        return data
    raw,ts,stale=_memo("cg:ids:"+",".join(ids),load,180,900)
    return {"source":"CoinGecko","fetched_at":ts,"stale":stale,
            "assets":[{
                "id":"coingecko:"+x["id"],"provider_id":x["id"],"name":x.get("name"),
                "symbol":x.get("symbol"),"rank":x.get("market_cap_rank"),
                "price_usd":_numeric(x.get("current_price")),
                "volume_24h_usd":_numeric(x.get("total_volume")),
                "market_cap_usd":_numeric(x.get("market_cap")),
                "change_24h_pct":_numeric(x.get("price_change_percentage_24h")),
                "market_status":"provider-reported-volume" if (_numeric(x.get("total_volume")) or 0)>0 else "volume-unavailable",
            } for x in raw if isinstance(x,dict) and x.get("id") in ids],
            "note":"An observed market quote is distinct from Silver Labs verification or exchange eligibility."}


def cmc_active(page=1,limit=100):
    if type(page) is not int or not 1<=page<=200:raise ValueError("page must be 1–200")
    if type(limit) is not int or not 1<=limit<=250:raise ValueError("limit must be 1–250")
    start=(page-1)*limit+1
    key=os.getenv("CMC_API_KEY","").strip()
    base=CMC+("/v3/cryptocurrency/listings/latest" if key else "/public-api/v3/cryptocurrency/listings/latest")
    params=urlencode({"start":start,"limit":limit,"convert":"USD"})
    def load():
        headers={"X-CMC_PRO_API_KEY":key} if key else {}
        data=_fetch(base+"?"+params,headers=headers)
        if not isinstance(data,dict) or not isinstance(data.get("data"),list):
            raise M.ProviderUnavailable("CMC active listing payload unavailable")
        return data
    raw,ts,stale=_memo("cmc:active:"+str(page)+":"+str(limit)+":"+str(bool(key)),load,300,900)
    assets=[]
    for item in raw["data"]:
        if not isinstance(item,dict):continue
        quote_data=item.get("quote")
        if isinstance(quote_data,list):
            quote_usd=next((x for x in quote_data if isinstance(x,dict) and x.get("symbol")=="USD"),{})
        elif isinstance(quote_data,dict):
            quote_usd=quote_data.get("USD",{})
        else:quote_usd={}
        if not isinstance(quote_usd,dict):quote_usd={}
        price=_numeric(quote_usd.get("price"));volume=_numeric(quote_usd.get("volume_24h"))
        if not price or not volume or price<=0 or volume<=0:continue
        cid=item.get("id")
        if type(cid) is not int:continue
        assets.append({"id":"coinmarketcap:"+str(cid),"provider_id":str(cid),
                       "name":item.get("name"),"symbol":item.get("symbol"),"rank":item.get("cmc_rank"),
                       "price_usd":price,"volume_24h_usd":volume,
                       "market_cap_usd":_numeric(quote_usd.get("market_cap")),
                       "change_24h_pct":_numeric(quote_usd.get("percent_change_24h")),
                       "source":"CoinMarketCap","market_status":"provider-reported-volume"})
    return {"source":"CoinMarketCap","page":page,"limit":limit,"assets":assets,
            "provider_rows":len(raw["data"]),"has_more":len(raw["data"])==limit,
            "fetched_at":ts,"stale":stale,"api_mode":"authenticated" if key else "keyless-public",
            "note":"Active provider listings with reported volume; visibility and permitted commercial use depend on your CMC plan."}


def coinbase_pairs(offset=0,limit=100):
    if type(offset) is not int or not 0<=offset<=10000:raise ValueError("offset must be 0–10000")
    if type(limit) is not int or not 1<=limit<=100:raise ValueError("limit must be 1–100")
    def load():
        raw=_fetch(COINBASE+"?"+urlencode({"limit":limit,"offset":offset,"product_type":"SPOT"}))
        if not isinstance(raw,dict) or not isinstance(raw.get("products"),list):
            raise M.ProviderUnavailable("Coinbase products unavailable")
        return raw
    raw,ts,stale=_memo(f"coinbase:products:{offset}:{limit}",load,300,900)
    pairs=[]
    for item in raw["products"]:
        if not isinstance(item,dict) or not isinstance(item.get("product_id"),str):continue
        if item.get("trading_disabled") or item.get("is_disabled") or item.get("status") in ("offline","delisted"):continue
        pairs.append({"id":"coinbase:"+item["product_id"],"pair":item["product_id"],
                      "base":item.get("base_currency_id"),"quote":item.get("quote_currency_id"),
                      "price":_numeric(item.get("price")),"volume_24h":_numeric(item.get("volume_24h")),
                      "source":"Coinbase Advanced Trade","status":item.get("status")})
    return {"source":"Coinbase Advanced Trade","fetched_at":ts,"stale":stale,
            "pairs":pairs,"offset":offset,"limit":limit,
            "provider_rows":len(raw["products"]),"has_more":len(raw["products"])==limit,
            "note":"Coinbase exchange products, not unique coin counts, global prices, or all-world availability."}


def news(limit=20):
    if type(limit) is not int or not 1<=limit<=40:raise ValueError("limit must be 1–40")
    def load():
        stories=[];sources=[]
        for publisher,(url,host) in FEEDS.items():
            try:
                raw=_fetch(url,kind="xml")
                root=ET.fromstring(raw)
                sources.append(publisher)
                for item in root.findall(".//item")[:20]:
                    title=" ".join((item.findtext("title") or "").split())[:180]
                    address=(item.findtext("link") or "").strip()
                    parsed=urlsplit(address)
                    if not title or parsed.scheme!="https" or not parsed.hostname or not (parsed.hostname==host or parsed.hostname.endswith("."+host)):
                        continue
                    published=item.findtext("pubDate") or ""
                    try:timestamp=int(parsedate_to_datetime(published).timestamp())
                    except (TypeError,ValueError,OverflowError):timestamp=None
                    stories.append({"source":publisher,"title":title,"url":address,
                                    "published_at":timestamp,
                                    "thumbnail_url":_rss_image(item,publisher),
                                    "favicon_url":PUBLISHER_FAVICONS.get(publisher)})
            except (M.ProviderUnavailable,ET.ParseError):
                continue
        if not sources:raise M.ProviderUnavailable("News publishers unavailable")
        unique={item["url"]:item for item in stories}
        # A publisher timestamp is separate from retrieval time.
        return {"articles":sorted(unique.values(),key=lambda x:x["published_at"] or 0,reverse=True),
                "sources":sources}
    data,ts,stale=_memo("news:rss:images:v2",load,900,3600)
    return {"source":"Publisher RSS feeds","sources":data["sources"],"articles":data["articles"][:limit],
            "fetched_at":ts,"stale":stale,
            "note":"Publisher RSS headlines, optional publisher-supplied thumbnails and favicons only; full articles remain at the original source. Images can be unavailable."}


def cg_trending():
    """Trending searches, not investment recommendations or verified listings."""
    def load():
        value=_fetch(CG+"/search/trending")
        if not isinstance(value,dict) or not isinstance(value.get("coins"),list):
            raise M.ProviderUnavailable("Trending feed unavailable")
        return value
    raw,ts,stale=_memo("cg:discover:trending:v1",load,600,1800)
    coins=[]
    for entry in raw["coins"][:30]:
        item=entry.get("item") if isinstance(entry,dict) else None
        if not isinstance(item,dict) or not isinstance(item.get("id"),str) or not _ID.fullmatch(item["id"]):
            continue
        coins.append({"id":"coingecko:"+item["id"],"provider_id":item["id"],
                      "name":str(item.get("name") or "")[:120],
                      "symbol":str(item.get("symbol") or "")[:30],
                      "rank":item.get("market_cap_rank"),
                      "icon":M._coin_image(item.get("thumb")),
                      "market_status":"trending-search-unverified"})
    return {"source":"CoinGecko /search/trending","coins":coins,
            "fetched_at":ts,"stale":stale,
            "note":"Provider trending searches, not market rankings, buy signals, or independently verified tokens."}


def cg_categories(limit=35):
    """Provider category market-cap rankings, with source-observed daily change."""
    if type(limit) is not int or not 1<=limit<=50:
        raise ValueError("limit must be 1–50")
    def load():
        value=_fetch(CG+"/coins/categories?"+urlencode({"order":"market_cap_desc"}))
        if not isinstance(value,list):raise M.ProviderUnavailable("Category feed unavailable")
        return value
    raw,ts,stale=_memo("cg:discover:categories:v1",load,900,3600)
    items=[]
    for category in raw[:limit]:
        if not isinstance(category,dict) or not isinstance(category.get("id"),str):continue
        items.append({"id":category["id"][:100],"name":str(category.get("name") or "")[:140],
                      "market_cap_usd":_numeric(category.get("market_cap")),
                      "change_24h_pct":_numeric(category.get("market_cap_change_24h")),
                      "volume_24h_usd":_numeric(category.get("volume_24h")),
                      "updated_at":category.get("updated_at")})
    return {"source":"CoinGecko /coins/categories","categories":items,
            "fetched_at":ts,"stale":stale,
            "note":"Provider-defined sector categories; categories overlap and are not additive, and rankings may change."}


def cg_exchanges(page=1,limit=30):
    """Read-only exchange overview; trust scores are CoinGecko definitions."""
    if type(page) is not int or not 1<=page<=20:
        raise ValueError("page must be 1–20")
    if type(limit) is not int or not 1<=limit<=50:
        raise ValueError("limit must be 1–50")
    def load():
        value=_fetch(CG+"/exchanges?"+urlencode({"per_page":limit,"page":page}))
        if not isinstance(value,list):raise M.ProviderUnavailable("Exchange feed unavailable")
        return value
    raw,ts,stale=_memo(f"cg:discover:exchanges:{page}:{limit}",load,900,3600)
    items=[]
    for exchange in raw:
        if not isinstance(exchange,dict) or not isinstance(exchange.get("id"),str):continue
        website=exchange.get("url")
        parts=urlsplit(website) if isinstance(website,str) and len(website)<700 else None
        if parts and (parts.scheme!="https" or not parts.hostname or parts.username or parts.password):
            website=None
        items.append({"id":exchange["id"][:120],
                      "name":str(exchange.get("name") or "")[:120],
                      "country":str(exchange.get("country") or "")[:100],
                      "year_established":exchange.get("year_established") if type(exchange.get("year_established")) is int else None,
                      "rank":exchange.get("trust_score_rank") if type(exchange.get("trust_score_rank")) is int else None,
                      "trust_score":_numeric(exchange.get("trust_score")),
                      "trade_volume_24h_btc":_numeric(exchange.get("trade_volume_24h_btc")),
                      "website":website})
    return {"source":"CoinGecko /exchanges","exchanges":items,"page":page,
            "has_more":len(raw)==limit,"fetched_at":ts,"stale":stale,
            "note":"External exchange information, not Silver Labs recommendations, a safety certification, or SilvEx trade volume."}


def cmc_exchange_map(page=1,limit=50):
    """Active exchange identities, NOT CMC volume/trust rankings.

    The CMC /exchange/listings/latest metrics require Growth tier or above.
    Keyless /exchange/map returns exchange identities and tracked status only.
    """
    if type(page) is not int or not 1<=page<=100:
        raise ValueError("page must be 1–100")
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError("limit must be 1–100")
    key=os.getenv("CMC_API_KEY","").strip()
    start=(page-1)*limit+1
    base=CMC+("/v1/exchange/map" if key else "/public-api/v1/exchange/map")
    url=base+"?"+urlencode({"start":start,"limit":limit,"listing_status":"active"})
    def load():
        value=_fetch(url,headers={"X-CMC_PRO_API_KEY":key} if key else {})
        if not isinstance(value,dict) or not isinstance(value.get("data"),list):
            raise M.ProviderUnavailable("CMC exchange identity map unavailable")
        return value
    raw,ts,stale=_memo(f"cmc:exchange-map:{page}:{limit}:{bool(key)}",load,900,3600)
    out=[]
    for item in raw["data"]:
        if not isinstance(item,dict) or type(item.get("id")) is not int:continue
        out.append({"id":"coinmarketcap:"+str(item["id"]),
                    "name":str(item.get("name") or "")[:120],
                    "slug":str(item.get("slug") or "")[:120],
                    "tracked":item.get("is_active")==1,
                    "status":str(item.get("status") or "unknown")[:30],
                    "rank":None,"volume_24h_btc":None,"trust_score":None,
                    "is_redistributable":item.get("is_redistributable")==1})
    return {"source":"CoinMarketCap /v1/exchange/map","exchanges":out,
            "fetched_at":ts,"stale":stale,"page":page,"limit":limit,
            "has_more":len(raw["data"])==limit,
            "note":"CMC exchange map contains provider identity and tracked state, not exchange volume or trust rankings. Paid listings/quotes access and redistribution rights must be separately verified."}


def cg_defi():
    """Global DeFi reference statistics supplied by CoinGecko."""
    def load():
        value=_fetch(CG+"/global/decentralized_finance_defi")
        if not isinstance(value,dict) or not isinstance(value.get("data"),dict):
            raise M.ProviderUnavailable("DeFi global data unavailable")
        return value
    raw,ts,stale=_memo("cg:discover:defi:v1",load,600,2400)
    item=raw["data"]
    return {"source":"CoinGecko /global/decentralized_finance_defi",
            "market_cap_usd":_numeric(item.get("defi_market_cap")),
            "volume_24h_usd":_numeric(item.get("trading_volume_24h")),
            "dominance_pct":_numeric(item.get("defi_dominance")),
            "defi_to_eth_ratio_pct":_numeric(item.get("defi_to_eth_ratio")),
            "top_coin_name":str(item.get("top_coin_name") or "")[:120],
            "fetched_at":ts,"stale":stale,
            "note":"Global provider DeFi estimates and asset categories change over time."}


def mining_estimate(inputs):
    """Simple expected-value calculator; requires explicit user-provided assumptions."""
    names=("miner_hashrate_hps","network_hashrate_hps","block_reward","blocks_per_day",
           "price_usd","fee_percent","power_watts","electricity_usd_per_kwh")
    if not isinstance(inputs,dict):raise ValueError("Expected explicit mining assumptions")
    values={}
    for n in names:
        v=_numeric(inputs.get(n))
        if v is None or v<0 or v>1e22:raise ValueError("Missing/invalid positive input: "+n)
        values[n]=v
    if values["network_hashrate_hps"]<=0 or values["blocks_per_day"]<=0 or values["miner_hashrate_hps"]<=0:
        raise ValueError("Hashrates and blocks per day must be greater than zero")
    if values["fee_percent"]>100:raise ValueError("fee_percent exceeds 100")
    if values["miner_hashrate_hps"]>values["network_hashrate_hps"]:
        raise ValueError("Miner hashrate cannot exceed total network hashrate")
    fraction=values["miner_hashrate_hps"]/values["network_hashrate_hps"]
    coins=values["block_reward"]*values["blocks_per_day"]*fraction*(1-values["fee_percent"]/100)
    gross=coins*values["price_usd"]
    electric=values["power_watts"]/1000*24*values["electricity_usd_per_kwh"]
    return {"coin_per_day_expected":coins,"gross_usd_per_day_expected":gross,
            "electricity_usd_per_day":electric,"net_usd_per_day_before_other_costs":gross-electric,
            "expected_network_share":fraction,"inputs":values,
            "note":"Illustrative expected values only; not actual revenue or an ROI guarantee. Ignores pool luck, stale shares, variance, hardware costs, depreciation, taxes, market liquidity and conversion fees."}
