"""SilverScan read-only direct market observations.

No accounts, trades, wallet calls, or private keys. Symbol names alone are NOT
verified chain asset identities. Collected quotes are venue-reported, not
SilverScan-verified market caps or consolidated volume.

This standalone module can be integrated with either SilverScan Python backend
without replacing the existing frontend.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


COINBASE = "https://api.exchange.coinbase.com"
KRAKEN = "https://api.kraken.com"
VENUES = ("coinbase", "kraken")
_PAIR = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_CURRENCY = re.compile(r"^[A-Za-z0-9.]{2,18}$")
_MAX_RESPONSE = 2_000_000


class VenueUnavailable(RuntimeError):
    """An external read-only data source could not be used."""


def decimal_text(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or (number <= 0 if positive else number < 0):
        return None
    return format(number, "f")


def fetch_json(url):
    """Only fixed public market-data hosts; no arbitrary URL proxy."""
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in
            ("api.exchange.coinbase.com", "api.kraken.com")
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise VenueUnavailable("Market data source not allowlisted")
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "SilverScan-ReadOnly-Market-Research/0.1",
    })
    try:
        with urlopen(request, timeout=8) as response:
            redirected = urlsplit(response.geturl())
            if redirected.scheme != "https" or redirected.hostname != parsed.hostname:
                raise VenueUnavailable("Market data redirect refused")
            payload = response.read(_MAX_RESPONSE + 1)
        if len(payload) > _MAX_RESPONSE:
            raise VenueUnavailable("Market data response exceeds limit")
        return json.loads(payload)
    except VenueUnavailable:
        raise
    except (OSError, ValueError, TimeoutError, json.JSONDecodeError) as exc:
        raise VenueUnavailable("Public market data unavailable") from exc


def _pair(venue, identifier, base, quoted, active=True):
    if not (isinstance(identifier, str) and _PAIR.fullmatch(identifier)
            and isinstance(base, str) and _CURRENCY.fullmatch(base)
            and isinstance(quoted, str) and _CURRENCY.fullmatch(quoted)):
        return None
    return {
        "venue": venue,
        "pair_id": identifier,
        "base": base.upper(),
        "quote": quoted.upper(),
        "active": bool(active),
        "verified_asset_identity": False,
    }


def list_pairs(venue, fetch=fetch_json):
    """Discover exchange-defined pairs; no assumed token-chain mapping."""
    if venue == "coinbase":
        rows = fetch(COINBASE + "/products")
        if not isinstance(rows, list):
            raise VenueUnavailable("Unexpected Coinbase products response")
        pairs = [
            _pair("coinbase", x.get("id"), x.get("base_currency"),
                  x.get("quote_currency"),
                  x.get("status") == "online" and not x.get("trading_disabled"))
            for x in rows if isinstance(x, dict)
        ]
    elif venue == "kraken":
        data = fetch(KRAKEN + "/0/public/AssetPairs")
        if not isinstance(data, dict) or data.get("error") or not isinstance(data.get("result"), dict):
            raise VenueUnavailable("Unexpected Kraken pairs response")
        pairs = []
        for key, value in data["result"].items():
            if not isinstance(value, dict) or not isinstance(value.get("wsname"), str):
                continue
            parts = value["wsname"].split("/")
            if len(parts) != 2:
                continue
            # Normalized symbol is only a display label, never a token identity.
            base = "BTC" if parts[0] == "XBT" else parts[0]
            q = "BTC" if parts[1] == "XBT" else parts[1]
            pairs.append(_pair("kraken", key, base, q,
                               value.get("status", "online") == "online"))
    else:
        raise ValueError("Unsupported exchange")
    return sorted((x for x in pairs if x is not None), key=lambda x: x["pair_id"])


def get_ticker(venue, pair, fetch=fetch_json, clock=time.time):
    if venue not in VENUES or pair.get("venue") != venue or not _PAIR.fullmatch(pair.get("pair_id", "")):
        raise ValueError("Invalid venue or pair")
    if venue == "coinbase":
        data = fetch(COINBASE + "/products/" + quote(pair["pair_id"], safe="") + "/ticker")
        if not isinstance(data, dict):
            raise VenueUnavailable("Invalid Coinbase ticker")
        price = data.get("price")
        base_volume = data.get("volume")
        source_time = data.get("time") if isinstance(data.get("time"), str) else None
    else:
        data = fetch(KRAKEN + "/0/public/Ticker?" + urlencode({"pair": pair["pair_id"]}))
        results = data.get("result") if isinstance(data, dict) and not data.get("error") else None
        # Kraken may return a canonical pair key differing from its request alias.
        if not isinstance(results, dict) or len(results) != 1:
            raise VenueUnavailable("Unexpected Kraken ticker")
        item = next(iter(results.values()))
        if not isinstance(item, dict):
            raise VenueUnavailable("Invalid Kraken ticker")
        price = (item.get("c") or [None])[0]
        volume = item.get("v") or []
        base_volume = volume[1] if isinstance(volume, list) and len(volume) > 1 else None
        source_time = None
    price_text = decimal_text(price, positive=True)
    volume_text = decimal_text(base_volume)
    if price_text is None:
        raise VenueUnavailable("Source did not return a valid positive price")
    return {
        "venue": venue,
        "pair_id": pair["pair_id"],
        "price_in_quote": price_text,
        "base_volume_24h": volume_text,
        "quote_currency": pair["quote"],
        "base_currency": pair["base"],
        "source_time": source_time,
        "observed_at": int(clock()),
        "quality": "venue-reported; identity-unverified",
    }


class VenueStore:
    """Small local SQLite store; use a dedicated DB or migrate for larger scale."""

    def __init__(self, path):
        self.path = str(Path(path))
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _db(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.execute("PRAGMA busy_timeout=10000")
        return con

    def _init(self):
        with self._db() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS venue_pairs (
                venue TEXT NOT NULL, pair_id TEXT NOT NULL, base TEXT NOT NULL,
                quote TEXT NOT NULL, active INTEGER NOT NULL,
                verified_asset_identity INTEGER NOT NULL DEFAULT 0,
                first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
                PRIMARY KEY (venue, pair_id))""")
            con.execute("""CREATE TABLE IF NOT EXISTS venue_observations (
                id INTEGER PRIMARY KEY, venue TEXT NOT NULL, pair_id TEXT NOT NULL,
                observed_at INTEGER NOT NULL, source_time TEXT,
                price_in_quote TEXT NOT NULL, base_volume_24h TEXT,
                quote_currency TEXT NOT NULL, quality TEXT NOT NULL,
                FOREIGN KEY (venue, pair_id) REFERENCES venue_pairs(venue, pair_id))""")
            con.execute("CREATE INDEX IF NOT EXISTS idx_venue_latest ON venue_observations(venue,pair_id,observed_at DESC)")
            con.execute("""CREATE TABLE IF NOT EXISTS venue_health (
                venue TEXT PRIMARY KEY, last_attempt INTEGER NOT NULL,
                last_success INTEGER, status TEXT NOT NULL, error TEXT)""")

    def upsert_pairs(self, pairs, observed_at=None):
        now = int(time.time()) if observed_at is None else int(observed_at)
        with self._db() as con:
            for p in pairs:
                con.execute("""INSERT INTO venue_pairs
                    (venue,pair_id,base,quote,active,verified_asset_identity,first_seen,last_seen)
                    VALUES (?,?,?,?,?,0,?,?)
                    ON CONFLICT(venue,pair_id) DO UPDATE SET
                    base=excluded.base,quote=excluded.quote,
                    active=excluded.active,last_seen=excluded.last_seen""",
                    (p["venue"],p["pair_id"],p["base"],p["quote"],
                     int(p["active"]),now,now))

    def save_ticker(self, tick):
        with self._db() as con:
            con.execute("""INSERT INTO venue_observations
                (venue,pair_id,observed_at,source_time,price_in_quote,
                 base_volume_24h,quote_currency,quality)
                VALUES (?,?,?,?,?,?,?,?)""",
                (tick["venue"],tick["pair_id"],tick["observed_at"],
                 tick["source_time"],tick["price_in_quote"],
                 tick["base_volume_24h"],tick["quote_currency"],tick["quality"]))

    def health(self, venue, status, error=None, observed_at=None):
        now = int(time.time()) if observed_at is None else int(observed_at)
        with self._db() as con:
            con.execute("""INSERT INTO venue_health
                (venue,last_attempt,last_success,status,error)
                VALUES (?,?,?,?,?)
                ON CONFLICT(venue) DO UPDATE SET
                last_attempt=excluded.last_attempt,
                last_success=COALESCE(excluded.last_success,venue_health.last_success),
                status=excluded.status,error=excluded.error""",
                (venue, now, now if status == "ok" else None, status, error))

    def latest(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("Invalid limit")
        with self._db() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("""SELECT o.venue,o.pair_id,p.base,p.quote,
                o.observed_at,o.source_time,o.price_in_quote,o.base_volume_24h,
                o.quality,p.verified_asset_identity
                FROM venue_observations AS o
                JOIN venue_pairs AS p ON p.venue=o.venue AND p.pair_id=o.pair_id
                WHERE o.id=(SELECT o2.id FROM venue_observations AS o2
                  WHERE o2.venue=o.venue AND o2.pair_id=o.pair_id
                  ORDER BY o2.observed_at DESC,o2.id DESC LIMIT 1)
                ORDER BY o.observed_at DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def sources(self):
        with self._db() as con:
            con.row_factory=sqlite3.Row
            return [dict(x) for x in con.execute(
                "SELECT * FROM venue_health ORDER BY venue").fetchall()]


def capture(venue, store, *, limit=5, quote_currencies=("USD","USDT"), fetch=fetch_json, clock=time.time):
    """One bounded batch; no silent background processes or unlicensed redistribution."""
    if venue not in VENUES or type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError("Invalid venue or request limit")
    now=int(clock())
    try:
        all_pairs=list_pairs(venue, fetch)
        store.upsert_pairs(all_pairs, observed_at=now)
        chosen=[p for p in all_pairs if p["active"] and p["quote"] in quote_currencies][:limit]
        saved=0
        errors=0
        for pair in chosen:
            try:
                store.save_ticker(get_ticker(venue,pair,fetch,clock))
                saved+=1
            except VenueUnavailable:
                errors+=1
        status="ok" if saved and not errors else "partial" if saved else "unavailable"
        store.health(venue,status,None if status=="ok" else "One or more ticker requests failed",now)
        return {"venue":venue,"pairs_discovered":len(all_pairs),"sampled":len(chosen),
                "observations_saved":saved,"ticker_errors":errors,"status":status}
    except VenueUnavailable:
        store.health(venue,"unavailable","Upstream market feed failed",now)
        return {"venue":venue,"pairs_discovered":0,"sampled":0,
                "observations_saved":0,"ticker_errors":0,"status":"unavailable"}


def main():
    parser=argparse.ArgumentParser(description="Bounded read-only SilverScan direct market research")
    parser.add_argument("--db",default="data/silverscan-venues.sqlite3")
    parser.add_argument("--venue",choices=VENUES,required=True)
    parser.add_argument("--limit",type=int,default=5)
    args=parser.parse_args()
    store=VenueStore(args.db)
    print(json.dumps(capture(args.venue,store,limit=args.limit),sort_keys=True))


if __name__ == "__main__":
    main()
