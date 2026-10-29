"""Read-only HTTP integration adapter for SilverScan direct-venue observations.

Call handle_get(path, store) from either SilverScan local server. The caller
serializes the returned JSON. This module performs no outbound network calls.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from app.direct_venue_data import VenueStore

ROUTES = {
    "/api/direct-venues/latest",
    "/api/direct-venues/sources",
}


def handle_get(path_with_query: str, store: VenueStore) -> tuple[int, dict] | None:
    """Return (HTTP status, JSON body) or None when this is not our route."""
    url = urlsplit(path_with_query)
    if url.path not in ROUTES:
        return None
    try:
        query = parse_qs(url.query, max_num_fields=3, strict_parsing=True)
        if url.path == "/api/direct-venues/sources":
            if query:
                raise ValueError("Unexpected query parameters")
            return 200, {
                "sources": store.sources(),
                "checked_live": False,
                "note": "Recorded source status only. No live probe made by this endpoint.",
            }
        if set(query) - {"limit"}:
            raise ValueError("Unexpected query parameters")
        values = query.get("limit", ["50"])
        if len(values) != 1 or not values[0].isascii() or not values[0].isdecimal():
            raise ValueError("Invalid limit")
        limit = int(values[0])
        return 200, {
            "observations": store.latest(limit),
            "data_kind": "last-trade-price-snapshots",
            "coverage": "limited sampled pairs, not the full exchange trade tape",
            "source": "Direct venue public REST",
            "verified_asset_identity": False,
            "note": "The 24h base volume is a rolling venue value. Never sum it over sampled observations.",
        }
    except ValueError:
        return 400, {"error": "Invalid direct market observations query"}
