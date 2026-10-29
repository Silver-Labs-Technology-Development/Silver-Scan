"""Read-only sample histories and market heatmaps for SilverScan.

Calculations are based only on locally recorded venue last-price samples.
They are NOT traded candles, volume-weighted rankings, coin market-cap heatmaps
or canonical blockchain asset identifications. Zero network access.
"""
from __future__ import annotations

from decimal import Decimal
import math
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit

from app.market_insights import (
    FRESH_SECONDS, MARKET_ID, MAX_PAIRS, VENUES, WINDOWS,
    _percent, _validated_price,
)

HISTORY_WINDOWS = {**WINDOWS, "30d": 2_592_000, "90d": 7_776_000, "1y": 31_536_000}
QUOTE_CURRENCIES = {"USD", "USDC", "USDT"}
_MAX_HISTORY_POINTS = 500


class HistoryStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)

    def _db(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def series(self, venue, market, window="24h", limit=180, as_of=None):
        """Bucket the *actual* sampled points, retaining the last observation
        in each interval. No smoothing, inferred trades or interpolated points.
        """
        if venue not in VENUES or not isinstance(market, str) or not MARKET_ID.fullmatch(market) or ".." in market:
            raise ValueError("Invalid venue market")
        if window not in HISTORY_WINDOWS or type(limit) is not int or not 2 <= limit <= _MAX_HISTORY_POINTS:
            raise ValueError("Invalid history window or point limit")
        now = int(time.time() if as_of is None else as_of)
        if now < 0:
            raise ValueError("Invalid timestamp")
        seconds = HISTORY_WINDOWS[window]
        start = max(0, now - seconds)
        # At most 'limit' inclusive time buckets, including boundary samples.
        bucket_seconds = max(1, math.ceil(seconds / (limit - 1)))
        with self._db() as db:
            registered = db.execute(
                "SELECT base,quote FROM venue_markets WHERE venue=? AND market_id=?",
                (venue, market),
            ).fetchone()
            if registered is None:
                return {"venue": venue, "market_id": market, "window": window,
                        "status": "market_not_in_directory", "points": [],
                        "sample_count": 0,
                        "note": "This venue market is not registered in the local directory."}
            overview = db.execute("""SELECT COUNT(*) n, MIN(observed_at) first_at,
                MAX(observed_at) last_at FROM venue_snapshots
                WHERE venue=? AND market_id=? AND observed_at BETWEEN ? AND ?""",
                (venue, market, start, now),
            ).fetchone()
            # In-database bucketing avoids loading an unbounded history into memory.
            raw = db.execute("""SELECT s.observed_at,s.last_price,s.source_time,s.source
                FROM venue_snapshots s
                JOIN (
                    SELECT MAX(observed_at) selected_at
                    FROM venue_snapshots
                    WHERE venue=? AND market_id=? AND observed_at BETWEEN ? AND ?
                    GROUP BY CAST((observed_at - ?) / ? AS INTEGER)
                ) chosen ON s.observed_at=chosen.selected_at
                WHERE s.venue=? AND s.market_id=?
                ORDER BY s.observed_at LIMIT ?""",
                (venue, market, start, now, start, bucket_seconds, venue, market, limit),
            ).fetchall()
        points = []
        for row in raw:
            price = _validated_price(row["last_price"])
            if price is None:
                continue
            points.append({"observed_at": int(row["observed_at"]),
                           "last_price_in_quote": str(price),
                           "source_time": row["source_time"], "source": row["source"]})
        last_at = overview["last_at"]
        age = now - int(last_at) if last_at is not None else None
        status = ("no_observations" if int(overview["n"]) == 0
                  else "stale" if age is not None and age > FRESH_SECONDS
                  else "insufficient_samples" if int(overview["n"]) < 2
                  else "sampled")
        gaps = [b["observed_at"] - a["observed_at"] for a, b in zip(points, points[1:])]
        return {"venue": venue, "market_id": market, "base_symbol": registered["base"],
                "quote_symbol": registered["quote"], "window": window, "as_of": now,
                "status": status, "sample_count": int(overview["n"]),
                "points_returned": len(points), "bucket_seconds": bucket_seconds,
                "first_observed_at": overview["first_at"],
                "last_observed_at": last_at,
                "last_observation_age_seconds": age,
                "largest_gap_between_displayed_points_seconds": max(gaps, default=None),
                "asset_identity_verified": False,
                "series_type": "sampled_last_traded_price",
                "points": points,
                "note": "Observed last prices only. Missing time intervals are unfilled. "
                        "No OHLCV, traded volume, market cap, or guaranteed executable quote."}

    def heatmap(self, venue, window="24h", quote_currency="USD", limit=100, as_of=None):
        """Sort observed pair price changes for one venue and one quote currency.

        Limits/bounds are deliberate; results are NOT the top-100 coins or a
        cap-weighted heatmap. The quote currency isn't converted into USD.
        """
        if (venue not in VENUES or window not in WINDOWS
                or quote_currency not in QUOTE_CURRENCIES
                or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError("Invalid heatmap query")
        now = int(time.time() if as_of is None else as_of)
        if now < 0:
            raise ValueError("Invalid timestamp")
        seconds = WINDOWS[window]
        anchor = now - seconds
        tolerance = max(120, seconds // 10)
        with self._db() as db:
            markets = db.execute("""SELECT m.venue,m.market_id,m.base,m.quote,
                 s.observed_at,s.last_price
                 FROM venue_markets m
                 JOIN venue_snapshots s ON s.rowid=(
                     SELECT x.rowid FROM venue_snapshots x
                     WHERE x.venue=m.venue AND x.market_id=m.market_id
                     AND x.observed_at <= ? ORDER BY x.observed_at DESC LIMIT 1)
                 WHERE m.venue=? AND m.quote=?
                 ORDER BY m.market_id LIMIT ?""",
                 (now, venue, quote_currency, MAX_PAIRS),
            ).fetchall()
            cells = []
            fresh = 0
            missing_reference = 0
            for row in markets:
                recent_at = int(row["observed_at"])
                if not 0 <= now - recent_at <= FRESH_SECONDS:
                    continue
                current = _validated_price(row["last_price"])
                if current is None:
                    continue
                fresh += 1
                prior = db.execute("""SELECT observed_at,last_price
                    FROM venue_snapshots
                    WHERE venue=? AND market_id=?
                      AND observed_at BETWEEN ? AND ? AND observed_at < ?
                    ORDER BY ABS(observed_at-?) ASC, observed_at DESC LIMIT 1""",
                    (venue, row["market_id"], anchor-tolerance, anchor+tolerance,
                     recent_at, anchor),
                ).fetchone()
                before = _validated_price(prior["last_price"]) if prior else None
                if before is None:
                    missing_reference += 1
                    continue
                change = (current - before) / before * Decimal(100)
                band = ("up-strong" if change >= 10 else "up" if change > 0
                        else "down-strong" if change <= -10
                        else "down" if change < 0 else "flat")
                cells.append({
                    "venue": venue, "market_id": row["market_id"],
                    "base_symbol": row["base"], "quote_symbol": quote_currency,
                    "last_price_in_quote": str(current),
                    "prior_price_in_quote": str(before),
                    "change_percent": _percent(change),
                    "band": band,
                    "first_observed_at": int(prior["observed_at"]),
                    "last_observed_at": recent_at,
                    "asset_identity_verified": False,
                })
        cells.sort(key=lambda c: (-Decimal(c["change_percent"]), c["market_id"]))
        return {"venue": venue, "window": window, "quote_currency": quote_currency,
                "as_of": now, "status": "sampled" if cells else "insufficient_history",
                "cells": cells[:limit], "pairs_scanned": len(markets),
                "pairs_with_fresh_samples": fresh,
                "pairs_missing_comparable_reference": missing_reference,
                "pairs_with_comparable_history": len(cells),
                "directory_scan_cap": MAX_PAIRS, "returned_cap": limit,
                "max_staleness_seconds": FRESH_SECONDS,
                "metric": "sampled_pair_price_percent_change",
                "size_metric": None,
                "note": "Single-venue sampled pairs with matching quote currency, "
                        "NOT a market-cap-weighted top-100 coin heatmap or verified token ranking."}


_ROUTES = {"/api/insights/local/series", "/api/insights/local/heatmap"}


def handle_get(uri: str, store: HistoryStore):
    """Return (HTTP status, JSON) or None; no network calls or writes."""
    url = urlsplit(uri)
    if url.path not in _ROUTES:
        return None
    try:
        params = parse_qs(url.query, keep_blank_values=True, max_num_fields=5)
        def one(key, default=""):
            values = params.get(key, [default])
            if len(values) != 1 or not isinstance(values[0], str) or len(values[0]) > 100:
                raise ValueError("Invalid parameter")
            return values[0]
        def positive_int(key, default):
            value = one(key, str(default))
            if not value.isascii() or not value.isdecimal():
                raise ValueError("Invalid numeric parameter")
            return int(value)
        if url.path.endswith("/series"):
            if set(params) - {"venue", "market", "window", "limit"}:
                raise ValueError("Unexpected query parameter")
            result = store.series(one("venue"), one("market"),
                                  one("window", "24h"), positive_int("limit", 180))
        else:
            if set(params) - {"venue", "quote", "window", "limit"}:
                raise ValueError("Unexpected query parameter")
            result = store.heatmap(one("venue"), one("window", "24h"),
                                   one("quote", "USD"), positive_int("limit", 100))
        return 200, result
    except ValueError:
        return 400, {"error": "Invalid read-only history/heatmap request"}
    except sqlite3.Error:
        return 503, {"error": "Local market history database unavailable"}
