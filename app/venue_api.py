"""Read-only local HTTP adapter for SilverScan venue_observations.

Call handle_get(url, store) from either version of SilverScan's local server.
Do not expose publicly without verifying exchange data-display rights.
"""
from urllib.parse import parse_qs, urlsplit
from app.venue_observations import VenueStore, VenueError

def _one(params, key, default=""):
    values=params.get(key,[default])
    if len(values)!=1 or len(values[0])>100:
        raise ValueError("Invalid parameter")
    return values[0]

def handle_get(uri: str, store: VenueStore):
    """Return (status, JSON) for supported GET routes, or None otherwise."""
    url=urlsplit(uri)
    path=url.path
    if path not in ("/api/venues/sources","/api/venues/markets","/api/venues/history"):
        return None
    try:
        query=parse_qs(url.query,keep_blank_values=True,max_num_fields=5)
        if path.endswith("/sources"):
            if query: raise ValueError("Unknown query")
            return 200, {"sources":store.sources(),"live_probed":False}
        venue=_one(query,"venue")
        raw_limit=_one(query,"limit","50")
        if not raw_limit.isascii() or not raw_limit.isdecimal():
            raise ValueError("Invalid limit")
        limit=int(raw_limit)
        if path.endswith("/markets"):
            if set(query)-{"venue","limit"}: raise ValueError("Unknown query")
            return 200, {
                "venue":venue,"markets":store.markets(venue,limit),
                "source":"Direct venue REST","coverage":"sampled-and-limited",
                "note":"Not full trade tape, complete coin catalog or market capitalization"
            }
        if set(query)-{"venue","market","limit"}: raise ValueError("Unknown query")
        market=_one(query,"market")
        return 200, {
            "venue":venue,"market_id":market,"points":store.history(venue,market,limit),
            "source":"Direct venue REST","series_type":"sampled_last_trade_price",
            "note":"NOT traded OHLCV; never sum rolling 24h volumes over samples"
        }
    except (ValueError,VenueError):
        return 400, {"error":"Invalid venue observation query"}
