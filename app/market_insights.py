"""Local, read-only market insights calculated from SilverScan venue samples.

These are *sample-to-sample* price changes, not executed-trade OHLCV.
Cross-venue comparison requires manual, documented base AND quote asset mapping.
No direct network requests, trading, transfers or privileged API endpoints.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import json
import re
import sqlite3
import time

VENUES = ("coinbase", "kraken")
WINDOWS = {"1h": 3600, "24h": 86400, "7d": 604800}
ASSET = re.compile(
    r"^(?:native:(?:bitcoin|ethereum|solana|bnb)|fiat:[A-Z]{3}|"
    r"eip155:[0-9]{1,10}/erc20:0x[a-fA-F0-9]{40}|"
    r"solana:mainnet/spl:[1-9A-HJ-NP-Za-km-z]{32,44})$"
)
MARKET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,89}$")
MAX_PAIRS = 500
FRESH_SECONDS = 300


def _validated_price(value):
    try:
        result = Decimal(value)
        return result if result.is_finite() and result > 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _percent(value):
    return format(value.quantize(Decimal("0.0001")), "f")


class InsightStore:
    def __init__(self, db_path):
        self.path = str(Path(db_path))

    def _db(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_mappings(self):
        """Only explicit local-operator initialization; no external APIs."""
        with self._db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS reviewed_market_mappings (
              venue TEXT NOT NULL, market_id TEXT NOT NULL,
              base_asset TEXT NOT NULL, quote_asset TEXT NOT NULL,
              evidence_url TEXT NOT NULL, reviewed_at INTEGER NOT NULL,
              PRIMARY KEY (venue,market_id)
            )""")

    def review_mapping(self, venue, market_id, base_asset, quote_asset, evidence_url, at=None):
        """Operator-only local method. NEVER expose this as an HTTP route."""
        if venue not in VENUES or not isinstance(market_id, str) or not MARKET_ID.fullmatch(market_id):
            raise ValueError("Invalid venue pair")
        if not all(isinstance(x, str) and ASSET.fullmatch(x) for x in (base_asset, quote_asset)):
            raise ValueError("Use explicit native/CAIP-like asset identity")
        if not isinstance(evidence_url, str) or len(evidence_url) > 400:
            raise ValueError("Public evidence HTTPS URL required")
        url = urlsplit(evidence_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.port not in (None, 443) or url.fragment):
            raise ValueError("Public evidence HTTPS URL required")
        when = int(time.time() if at is None else at)
        self.initialize_mappings()
        with self._db() as conn:
            if conn.execute("SELECT 1 FROM venue_markets WHERE venue=? AND market_id=?",
                            (venue,market_id)).fetchone() is None:
                raise ValueError("Pair must first be observed in venue directory")
            conn.execute("""INSERT INTO reviewed_market_mappings
              (venue,market_id,base_asset,quote_asset,evidence_url,reviewed_at)
              VALUES (?,?,?,?,?,?) ON CONFLICT(venue,market_id) DO UPDATE SET
              base_asset=excluded.base_asset,quote_asset=excluded.quote_asset,
              evidence_url=excluded.evidence_url,reviewed_at=excluded.reviewed_at""",
              (venue,market_id,base_asset,quote_asset,evidence_url,when))

    def movers(self, venue, window="24h", limit=10, as_of=None):
        if venue not in VENUES or window not in WINDOWS or type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("Unsupported venue, window or limit")
        now = int(time.time() if as_of is None else as_of)
        horizon = WINDOWS[window]
        anchor = now - horizon
        tolerance = max(120, horizon // 10)
        with self._db() as conn:
            pairs = conn.execute("""SELECT m.venue,m.market_id,m.base,m.quote,
               s.observed_at,s.last_price
               FROM venue_markets m JOIN venue_snapshots s ON s.rowid=(
                   SELECT x.rowid FROM venue_snapshots x
                   WHERE x.venue=m.venue AND x.market_id=m.market_id
                   AND x.observed_at<=? ORDER BY x.observed_at DESC LIMIT 1)
               WHERE m.venue=? ORDER BY m.market_id LIMIT ?""", (now,venue,MAX_PAIRS)).fetchall()
            result = []
            fresh = 0
            for p in pairs:
                latest_at = int(p["observed_at"])
                if not 0 <= now - latest_at <= FRESH_SECONDS:
                    continue
                fresh += 1
                latest = _validated_price(p["last_price"])
                if latest is None:
                    continue
                prior = conn.execute("""SELECT observed_at,last_price
                    FROM venue_snapshots WHERE venue=? AND market_id=?
                    AND observed_at BETWEEN ? AND ? AND observed_at < ?
                    ORDER BY ABS(observed_at-?) ASC,observed_at DESC LIMIT 1""",
                    (venue,p["market_id"],anchor-tolerance,anchor+tolerance,latest_at,anchor)).fetchone()
                if prior is None:
                    continue
                price_before = _validated_price(prior["last_price"])
                if price_before is None:
                    continue
                result.append({
                    "venue":venue,"market_id":p["market_id"],
                    "base_symbol":p["base"],"quote_symbol":p["quote"],
                    "from_price":str(price_before),"to_price":str(latest),
                    "change_pct":_percent((latest-price_before)/price_before*100),
                    "from_observed_at":int(prior["observed_at"]),
                    "to_observed_at":latest_at,
                    "period_observed_seconds":latest_at-int(prior["observed_at"]),
                    "asset_identity_verified":False,
                })
        gainers = sorted((x for x in result if Decimal(x["change_pct"]) > 0),
                         key=lambda x:(-Decimal(x["change_pct"]),x["market_id"]))[:limit]
        losers = sorted((x for x in result if Decimal(x["change_pct"]) < 0),
                        key=lambda x:(Decimal(x["change_pct"]),x["market_id"]))[:limit]
        return {"source":"SilverScan sampled venue observations","venue":venue,"window":window,
                "as_of":now,"gainers":gainers,"losers":losers,
                "sampled_pairs_scanned":len(pairs),"pairs_with_fresh_sample":fresh,
                "pairs_with_comparable_history":len(result),
                "selection_cap":MAX_PAIRS,"max_staleness_seconds":FRESH_SECONDS,
                "note":"Rankings are limited to sampled markets with two comparable observations. NOT venue-wide market movers, traded OHLCV, or an independently verified coin ranking."}

    def quality(self, as_of=None):
        now = int(time.time() if as_of is None else as_of)
        with self._db() as conn:
            status = {r["venue"]:dict(r) for r in conn.execute("SELECT * FROM venue_health")}
            result=[]
            for venue in VENUES:
                directory = conn.execute("SELECT COUNT(*) AS n FROM venue_markets WHERE venue=?", (venue,)).fetchone()["n"]
                latest = conn.execute("""SELECT MAX(x.observed_at) AS newest,
                   COUNT(*) AS sampled,
                   SUM(CASE WHEN x.observed_at BETWEEN ? AND ? THEN 1 ELSE 0 END) AS fresh
                   FROM (SELECT MAX(observed_at) AS observed_at FROM venue_snapshots
                         WHERE venue=? AND observed_at<=?
                         GROUP BY market_id) x""",(now-FRESH_SECONDS,now,venue,now)).fetchone()
                sampled = int(latest["sampled"] or 0)
                newest = latest["newest"]
                result.append({"venue":venue,"directory_pairs":directory,
                  "sampled_pairs":sampled,"fresh_pairs":int(latest["fresh"] or 0),
                  "last_observed_at":newest,
                  "last_observation_age_seconds":now-int(newest) if newest is not None else None,
                  "last_collection_status":status.get(venue,{}).get("status","never_polled"),
                  "last_attempt":status.get(venue,{}).get("last_attempt"),
                  "last_success":status.get(venue,{}).get("last_success")})
        return {"sources":result,"as_of":now,"stale_after_seconds":FRESH_SECONDS,
                "coverage":"sampled exchange markets only", "live_probed":False,
                "note":"Directory counts and locally sampled pairs do not constitute full chain or exchange coverage."}

    def cross_venue(self, base_asset, quote_asset, as_of=None):
        if not all(isinstance(x,str) and ASSET.fullmatch(x) for x in (base_asset,quote_asset)):
            raise ValueError("Exact asset identities required")
        now = int(time.time() if as_of is None else as_of)
        self.initialize_mappings()
        with self._db() as conn:
            rows=conn.execute("""SELECT r.venue,r.market_id,r.base_asset,r.quote_asset,
                    r.reviewed_at,r.evidence_url,s.observed_at,s.last_price,s.source
                  FROM reviewed_market_mappings r
                  JOIN venue_snapshots s ON s.rowid=(
                    SELECT x.rowid FROM venue_snapshots x
                    WHERE x.venue=r.venue AND x.market_id=r.market_id
                    AND x.observed_at<=? ORDER BY x.observed_at DESC LIMIT 1)
                  WHERE r.base_asset=? AND r.quote_asset=?
                  ORDER BY s.observed_at DESC,r.venue,r.market_id""",
                  (now,base_asset,quote_asset)).fetchall()
        observations=[]
        used=set()
        for row in rows:
            if row["venue"] in used or not 0 <= now-int(row["observed_at"]) <= FRESH_SECONDS:
                continue
            price=_validated_price(row["last_price"])
            if price is None:
                continue
            used.add(row["venue"])
            observations.append({"venue":row["venue"],"market_id":row["market_id"],
                 "price_in_quote_asset":str(price),"observed_at":row["observed_at"],
                 "source":row["source"],"mapping_status":"operator-reviewed",
                 "mapping_evidence":row["evidence_url"],"mapping_reviewed_at":row["reviewed_at"]})
        times=[x["observed_at"] for x in observations]
        time_spread=max(times)-min(times) if times else None
        comparable = len(observations)>=2 and time_spread<=120
        prices=[Decimal(x["price_in_quote_asset"]) for x in observations]
        spread = _percent((max(prices)-min(prices))/min(prices)*100) if comparable else None
        return {"base_asset":base_asset,"quote_asset":quote_asset,"observed_venues":observations,
                "as_of":now,"status":"comparable" if comparable else "insufficient_comparable_markets",
                "highest_vs_lowest_pct":spread if comparable else None,
                "maximum_observation_skew_seconds":120,"observed_skew_seconds":time_spread,
                "note":"Operator-reviewed mappings, not independently verified assets. Last-trade samples are not executable quotes or arbitrage opportunities. No fees, slippage or order-book depth included."}


_ROUTES = {"/api/insights/local/movers", "/api/insights/local/quality", "/api/insights/local/compare"}


def handle_get(uri: str, store: InsightStore):
    """Adapter: (HTTP status, body) for local GET; None for unrelated routes."""
    url=urlsplit(uri)
    if url.path not in _ROUTES:
        return None
    try:
        params=parse_qs(url.query,keep_blank_values=True,max_num_fields=5)
        def one(key,default=""):
            values=params.get(key,[default])
            if len(values)!=1 or len(values[0])>180:
                raise ValueError("Invalid parameter")
            return values[0]
        if url.path.endswith("/quality"):
            if params:
                raise ValueError("Unexpected parameters")
            return 200,store.quality()
        if url.path.endswith("/movers"):
            if set(params)-{"venue","window","limit"}:
                raise ValueError("Unexpected parameters")
            raw=one("limit","10")
            if not raw.isascii() or not raw.isdecimal():
                raise ValueError("Invalid limit")
            return 200,store.movers(one("venue"),one("window","24h"),int(raw))
        if set(params)-{"base_asset","quote_asset"}:
            raise ValueError("Unexpected parameters")
        return 200,store.cross_venue(one("base_asset"),one("quote_asset"))
    except ValueError:
        return 400,{"error":"Invalid read-only market insights request"}
    except sqlite3.Error:
        return 503,{"error":"Local observation database unavailable"}
