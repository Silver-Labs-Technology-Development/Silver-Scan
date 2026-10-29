"""SilverScan independent READ-ONLY exchange observation collector.

This module never places orders, handles wallet secrets, or proxies arbitrary URLs.
Snapshots are samples of last-trade prices, NOT a complete trade tape or OHLCV.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

SOURCE_URLS = {
    "coinbase": "https://api.exchange.coinbase.com",
    "kraken": "https://api.kraken.com",
}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,89}$")


class VenueError(Exception):
    """Source is invalid, unavailable, or rate-limited."""


def _safe_id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value) or ".." in value:
        raise VenueError("Invalid venue identifier")
    return value


def _number(value, *, positive=False):
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise VenueError("Missing or invalid numeric observation")
    try:
        n = Decimal(str(value))
    except InvalidOperation as exc:
        raise VenueError("Invalid numeric observation") from exc
    if not n.is_finite() or n < 0 or (positive and n == 0):
        raise VenueError("Invalid numeric observation")
    return format(n, "f")


def _iso_timestamp(value):
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(result.timestamp()) if result.tzinfo else None
    except ValueError:
        return None


def fetch_public(venue, path):
    """Fixed HTTPS hosts only; no API credentials, arbitrary RPC or redirects."""
    if venue not in SOURCE_URLS or not path.startswith("/") or "//" in path or ".." in path:
        raise VenueError("Unsupported market endpoint")
    url = SOURCE_URLS[venue] + path
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != urlsplit(SOURCE_URLS[venue]).netloc:
        raise VenueError("Untrusted market host")
    request = Request(url, headers={
        "Accept": "application/json", "User-Agent": "SilverScanReadOnly/0.1"
    })
    try:
        with urlopen(request, timeout=8) as response:
            if urlsplit(response.geturl()).netloc != parsed.netloc:
                raise VenueError("Market redirect rejected")
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise VenueError("Oversized market response")
        return json.loads(raw)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, UnicodeDecodeError) as exc:
        raise VenueError("Venue unavailable or rate-limited") from exc


@dataclass(frozen=True)
class Market:
    venue: str
    market_id: str
    base: str
    quote: str


@dataclass(frozen=True)
class Snapshot:
    venue: str
    market_id: str
    observed_at: int
    last_price: str
    volume_24h_base: str | None
    volume_24h_quote_estimate: str | None
    quote_estimate_method: str | None
    source_time: int | None
    source: str


def parse_markets(venue, payload):
    if venue == "coinbase":
        if not isinstance(payload, list):
            raise VenueError("Invalid Coinbase markets")
        result = []
        for row in payload[:10000]:
            if not isinstance(row, dict) or row.get("status") != "online" or row.get("trading_disabled"):
                continue
            try:
                result.append(Market(venue, _safe_id(row["id"]), _safe_id(row["base_currency"]),
                                     _safe_id(row["quote_currency"])))
            except (KeyError, VenueError):
                continue
        return result
    if venue == "kraken":
        if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("result"), dict):
            raise VenueError("Invalid Kraken markets")
        result = []
        for market_id, row in list(payload["result"].items())[:10000]:
            if not isinstance(row, dict) or row.get("status", "online") != "online":
                continue
            pair = row.get("wsname")
            if not isinstance(pair, str) or pair.count("/") != 1:
                continue
            a, b = pair.split("/")
            try:
                result.append(Market(venue, _safe_id(market_id), _safe_id(a), _safe_id(b)))
            except VenueError:
                pass
        return result
    raise VenueError("Unsupported venue")


def get_markets(venue, fetch: Callable = fetch_public):
    if venue == "coinbase":
        return parse_markets(venue, fetch(venue, "/products"))
    if venue == "kraken":
        return parse_markets(venue, fetch(venue, "/0/public/AssetPairs"))
    raise VenueError("Unsupported venue")


def get_snapshot(market: Market, fetch: Callable = fetch_public, clock: Callable = time.time):
    mid = _safe_id(market.market_id)
    now = int(clock())
    if market.venue == "coinbase":
        row = fetch("coinbase", "/products/" + quote(mid, safe="") + "/ticker")
        if not isinstance(row, dict):
            raise VenueError("Invalid Coinbase ticker")
        return Snapshot("coinbase", mid, now, _number(row.get("price"), positive=True),
                        _number(row["volume"]) if row.get("volume") is not None else None,
                        None, None, _iso_timestamp(row.get("time")), "Coinbase Exchange REST")
    if market.venue == "kraken":
        result = fetch("kraken", "/0/public/Ticker?" + urlencode({"pair": mid}))
        if not isinstance(result, dict) or result.get("error") or not isinstance(result.get("result"), dict):
            raise VenueError("Invalid Kraken ticker")
        items = result["result"]
        if len(items) != 1:
            raise VenueError("Ambiguous Kraken ticker")
        row = next(iter(items.values()))
        try:
            price = _number(row["c"][0], positive=True)
            volume = _number(row["v"][1])
            vwap = _number(row["p"][1], positive=True)
        except (TypeError, KeyError, IndexError) as exc:
            raise VenueError("Missing Kraken price or volume") from exc
        estimate = format(Decimal(volume) * Decimal(vwap), "f")
        return Snapshot("kraken", mid, now, price, volume, estimate,
                        "rolling_24h_vwap_times_base_volume", None, "Kraken Spot REST")
    raise VenueError("Unsupported venue")


class VenueStore:
    def __init__(self, path):
        self.path = str(path)

    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS venue_markets(
                venue TEXT NOT NULL, market_id TEXT NOT NULL,
                base TEXT NOT NULL, quote TEXT NOT NULL,
                first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
                PRIMARY KEY(venue, market_id)
            );
            CREATE TABLE IF NOT EXISTS venue_snapshots(
                venue TEXT NOT NULL, market_id TEXT NOT NULL, observed_at INTEGER NOT NULL,
                last_price TEXT NOT NULL, volume_24h_base TEXT,
                volume_24h_quote_estimate TEXT, quote_estimate_method TEXT,
                source_time INTEGER, source TEXT NOT NULL,
                PRIMARY KEY(venue, market_id, observed_at)
            );
            CREATE INDEX IF NOT EXISTS venue_snapshots_recent
                ON venue_snapshots(venue, market_id, observed_at DESC);
            CREATE TABLE IF NOT EXISTS venue_health(
                venue TEXT PRIMARY KEY, status TEXT NOT NULL, last_attempt INTEGER,
                last_success INTEGER, last_error TEXT
            );
            """)

    def register(self, markets, seen_at):
        with self._db() as db:
            db.executemany("""
                INSERT INTO venue_markets VALUES(?,?,?,?,?,?)
                ON CONFLICT(venue,market_id) DO UPDATE SET
                base=excluded.base,quote=excluded.quote,last_seen=excluded.last_seen
            """, [(m.venue,m.market_id,m.base,m.quote,seen_at,seen_at) for m in markets])

    def record(self, snapshot):
        with self._db() as db:
            found = db.execute("SELECT 1 FROM venue_markets WHERE venue=? AND market_id=?",
                               (snapshot.venue,snapshot.market_id)).fetchone()
            if found is None:
                raise VenueError("Market must be registered before an observation")
            db.execute("""
                INSERT OR IGNORE INTO venue_snapshots VALUES(?,?,?,?,?,?,?,?,?)
            """, (snapshot.venue,snapshot.market_id,snapshot.observed_at,snapshot.last_price,
                  snapshot.volume_24h_base,snapshot.volume_24h_quote_estimate,
                  snapshot.quote_estimate_method,snapshot.source_time,snapshot.source))

    def health(self, venue, status, now, error=None):
        if venue not in SOURCE_URLS or status not in ("ok", "unavailable"):
            raise ValueError("Invalid venue status")
        with self._db() as db:
            db.execute("""
                INSERT INTO venue_health VALUES(?,?,?,?,?)
                ON CONFLICT(venue) DO UPDATE SET
                  status=excluded.status,last_attempt=excluded.last_attempt,
                  last_success=COALESCE(excluded.last_success,venue_health.last_success),
                  last_error=excluded.last_error
            """, (venue,status,now,now if status=="ok" else None,
                  error[:160] if isinstance(error,str) else None))

    def sources(self):
        with self._db() as db:
            found={row["venue"]:dict(row) for row in db.execute("SELECT * FROM venue_health")}
        return [found.get(venue,{"venue":venue,"status":"never_polled","last_attempt":None,
                                 "last_success":None,"last_error":None}) for venue in sorted(SOURCE_URLS)]

    def markets(self, venue, limit=50):
        if venue not in SOURCE_URLS or not 1<=limit<=200:
            raise ValueError("Invalid venue or limit")
        with self._db() as db:
            rows=db.execute("""
                SELECT m.venue,m.market_id,m.base,m.quote,m.last_seen,
                    s.observed_at,s.last_price,s.volume_24h_base,
                    s.volume_24h_quote_estimate,s.quote_estimate_method,
                    s.source_time,s.source
                FROM venue_markets m LEFT JOIN venue_snapshots s ON s.rowid=(
                    SELECT x.rowid FROM venue_snapshots x
                    WHERE x.venue=m.venue AND x.market_id=m.market_id
                    ORDER BY x.observed_at DESC LIMIT 1)
                WHERE m.venue=? ORDER BY m.market_id LIMIT ?
            """,(venue,limit)).fetchall()
        return [dict(r) for r in rows]

    def history(self, venue, market_id, limit=100):
        if venue not in SOURCE_URLS or not 1<=limit<=500:
            raise ValueError("Invalid venue or limit")
        _safe_id(market_id)
        with self._db() as db:
            rows=db.execute("""
                SELECT observed_at,last_price,volume_24h_base,volume_24h_quote_estimate,
                       quote_estimate_method,source_time,source
                FROM venue_snapshots WHERE venue=? AND market_id=?
                ORDER BY observed_at DESC LIMIT ?
            """,(venue,market_id,limit)).fetchall()
        return [dict(r) for r in rows]


def poll_once(venue, store, ids=None, fetch=fetch_public, clock=time.time, pause=time.sleep):
    """One bounded read-only collection cycle; no background daemon."""
    ids=list(ids or [])
    if venue not in SOURCE_URLS or len(ids)>20:
        raise ValueError("Unknown venue or more than 20 requested markets")
    store.initialize()
    try:
        directory=get_markets(venue,fetch)
        store.register(directory,int(clock()))
        available={m.market_id:m for m in directory}
        selected=ids or [m.market_id for m in directory if m.quote in ("USD","USDC")][:5]
        if any(mid not in available for mid in selected):
            raise VenueError("Market identifier not found in current venue directory")
        observed=[]
        errors=[]
        for i,mid in enumerate(selected):
            if i:
                pause(.5)
            try:
                snapshot=get_snapshot(available[mid],fetch,clock)
                store.record(snapshot)
                observed.append(asdict(snapshot))
            except VenueError as exc:
                errors.append({"market_id":mid,"error":str(exc)})
        status="ok" if observed else "unavailable"
        store.health(venue,status,int(clock()),None if observed else "No valid observations")
        return {"venue":venue,"status":status,"observed":observed,"errors":errors,
                "coverage":"sampled_last_trade_prices","not_ohlcv":True}
    except VenueError as exc:
        store.health(venue,"unavailable",int(clock()),str(exc))
        return {"venue":venue,"status":"unavailable","observed":[],
                "errors":[{"error":str(exc)}],"coverage":"unavailable"}


def main(argv=None):
    parser=argparse.ArgumentParser(description="SilverScan READ-ONLY direct exchange samples")
    parser.add_argument("--venue",required=True,choices=sorted(SOURCE_URLS))
    parser.add_argument("--market",action="append",default=[],help="Venue-native pair ID, max 20")
    parser.add_argument("--db",default=os.environ.get("SILVERSCAN_VENUES_DB","data/venue_observations.sqlite3"))
    args=parser.parse_args(argv)
    outcome=poll_once(args.venue,VenueStore(args.db),args.market)
    print(json.dumps(outcome,indent=2))
    return 0 if outcome["status"]=="ok" else 1


if __name__=="__main__":
    sys.exit(main())
