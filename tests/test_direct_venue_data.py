"""Offline contract tests for direct venue observations. No internet access."""
from __future__ import annotations

import sqlite3
from decimal import Decimal
import pytest
from app.direct_venue_data import (
    VenueStore, VenueUnavailable, capture, decimal_text,
    fetch_json, get_ticker, list_pairs,
)


def source(url):
    if url == "https://api.exchange.coinbase.com/products":
        return [
            {"id":"BTC-USD","base_currency":"BTC","quote_currency":"USD",
             "status":"online","trading_disabled":False},
            {"id":"SOL-USD","base_currency":"SOL","quote_currency":"USD",
             "status":"online","trading_disabled":False},
            {"id":"BAD-USD","base_currency":"BAD","quote_currency":"USD",
             "status":"offline","trading_disabled":True},
            {"id":"invalid/pair","base_currency":"BAD","quote_currency":"USD",
             "status":"online"},
        ]
    if url.endswith("/products/BTC-USD/ticker"):
        return {"price":"67123.123456789012345678","volume":"6.125","time":"2026-10-29T12:00:00Z"}
    if url.endswith("/products/SOL-USD/ticker"):
        return {"price":"122.55","volume":"0","time":"2026-10-29T12:00:00Z"}
    if url == "https://api.kraken.com/0/public/AssetPairs":
        return {"error":[],"result":{
            "XXBTZUSD":{"wsname":"XBT/USD","status":"online"},
            "SOLEUR":{"wsname":"SOL/EUR","status":"online"},
            "MISSING":{"wsname":"bad-format"}}}
    if url == "https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD":
        return {"error":[],"result":{"XBTUSD":{"c":["67300.123456789","0.01"],
                            "v":["3.0","7.125"]}}}
    raise VenueUnavailable("Fixture request not implemented")


def test_decimal_precision_and_invalid_values():
    assert decimal_text("0.000000000000000001",positive=True)=="0.000000000000000001"
    assert decimal_text(Decimal("12.340000"))=="12.340000"
    for value in ("NaN","Infinity","-5","not-a-number",True,None,object()):
        assert decimal_text(value) is None
    assert decimal_text("0",positive=True) is None


def test_coinbase_pair_listing_filters_bad_ids_and_marks_offline():
    pairs=list_pairs("coinbase",source)
    assert [p["pair_id"] for p in pairs]==["BAD-USD","BTC-USD","SOL-USD"]
    assert pairs[0]["active"] is False
    assert pairs[1]["verified_asset_identity"] is False


def test_kraken_pair_listing_canonicalizes_display_not_identity():
    pairs=list_pairs("kraken",source)
    assert pairs[0]["pair_id"]=="SOLEUR"
    assert pairs[1]["base"]=="BTC"
    assert pairs[1]["quote"]=="USD"


def test_ticker_price_volume_and_source_attribution():
    pair=list_pairs("coinbase",source)[1]
    tick=get_ticker("coinbase",pair,source,clock=lambda:42)
    assert tick["observed_at"]==42
    assert tick["price_in_quote"]=="67123.123456789012345678"
    assert tick["base_volume_24h"]=="6.125"
    assert "identity-unverified" in tick["quality"]
    kraken=list_pairs("kraken",source)[1]
    tick=get_ticker("kraken",kraken,source,clock=lambda:43)
    assert tick["price_in_quote"]=="67300.123456789"
    assert tick["base_volume_24h"]=="7.125"


def test_bounded_collection_and_persistent_snapshot(tmp_path):
    store=VenueStore(tmp_path/"observations.sqlite3")
    result=capture("coinbase",store,limit=2,fetch=source,clock=lambda:100)
    assert result["status"]=="ok"
    assert result["observations_saved"]==2
    latest=VenueStore(tmp_path/"observations.sqlite3").latest()
    assert len(latest)==2
    assert {row["pair_id"] for row in latest}=={"BTC-USD","SOL-USD"}
    assert all(row["verified_asset_identity"]==0 for row in latest)
    assert len(store.sources())==1
    with pytest.raises(ValueError): capture("coinbase",store,limit=26,fetch=source)


def test_partial_failure_does_not_fabricate_quote(tmp_path):
    def broken(url):
        if url.endswith("/products/SOL-USD/ticker"):
            raise VenueUnavailable("offline")
        return source(url)
    store=VenueStore(tmp_path/"observations.sqlite3")
    result=capture("coinbase",store,limit=2,fetch=broken,clock=lambda:77)
    assert result["status"]=="partial"
    assert result["ticker_errors"]==1
    assert len(store.latest())==1
    assert store.sources()[0]["status"]=="partial"


def test_rejected_source_and_malformed_kraken_response(tmp_path):
    with pytest.raises(VenueUnavailable):
        fetch_json("http://api.kraken.com/0/public/Ticker")
    with pytest.raises(VenueUnavailable):
        fetch_json("https://example.org/steal")
    def bad_kraken(url):
        return {"error":["bad pair"],"result":{}}
    with pytest.raises(VenueUnavailable):
        list_pairs("kraken",bad_kraken)
    store=VenueStore(tmp_path/"observations.sqlite3")
    result=capture("kraken",store,fetch=bad_kraken)
    assert result["status"]=="unavailable"
    assert store.latest()==[]
    assert store.sources()[0]["last_success"] is None


def test_observations_append_and_latest_uses_newest(tmp_path):
    store=VenueStore(tmp_path/"observations.sqlite3")
    capture("coinbase",store,limit=1,fetch=source,clock=lambda:111)
    def updated(url):
        if url.endswith("/products/BTC-USD/ticker"):
            return {"price":"69000.000000001","volume":"7"}
        return source(url)
    capture("coinbase",store,limit=1,fetch=updated,clock=lambda:112)
    assert store.latest(1)[0]["price_in_quote"]=="69000.000000001"
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM venue_observations").fetchone()[0]==2
