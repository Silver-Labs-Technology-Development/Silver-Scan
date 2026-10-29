"""Offline tests: stub remote exchange responses; never use live funds."""
from pathlib import Path
import tempfile
import unittest

from app.venue_observations import (
    Market, VenueError, VenueStore, _number, _safe_id,
    parse_markets, get_snapshot, poll_once,
)
from app.venue_api import handle_get

COINBASE = [
    {"id":"BTC-USD","status":"online","base_currency":"BTC","quote_currency":"USD"},
    {"id":"SOL-USD","status":"offline","base_currency":"SOL","quote_currency":"USD"},
]
KRAKEN = {"error":[],"result":{
    "XXBTZUSD":{"wsname":"XBT/USD","status":"online"},
    "XETHZUSD":{"wsname":"ETH/USD","status":"cancel_only"},
}}
TICKER_CB = {"price":"100123.4500","volume":"8.125","time":"2026-10-29T19:00:00Z"}
TICKER_KR = {"error":[],"result":{"XXBTZUSD":{
    "c":["100000.1234","0.001"],"v":["2.3","4.2"],"p":["99000.2","99500.5"]
}}}

class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=VenueStore(Path(self.temp.name)/"venue.db")
        self.store.initialize()
    def tearDown(self):
        self.temp.cleanup()

    def test_coinbase_directory_only_online(self):
        self.assertEqual([m.market_id for m in parse_markets("coinbase",COINBASE)],["BTC-USD"])

    def test_kraken_directory_has_native_identity(self):
        m=parse_markets("kraken",KRAKEN)
        self.assertEqual((m[0].market_id,m[0].base),("XXBTZUSD","XBT"))
        self.assertEqual(len(m),1)

    def test_price_precision_and_quote_volume_unavailable(self):
        m=Market("coinbase","BTC-USD","BTC","USD")
        snapshot=get_snapshot(m,lambda venue,path:TICKER_CB,lambda:123)
        self.assertEqual(snapshot.last_price,"100123.4500")
        self.assertEqual(snapshot.volume_24h_base,"8.125")
        self.assertIsNone(snapshot.volume_24h_quote_estimate)
        self.assertIsNotNone(snapshot.source_time)

    def test_kraken_quote_volume_is_estimate(self):
        m=Market("kraken","XXBTZUSD","XBT","USD")
        value=get_snapshot(m,lambda venue,path:TICKER_KR,lambda:123)
        self.assertEqual(value.volume_24h_quote_estimate,"417902.10")
        self.assertIn("vwap",value.quote_estimate_method)

    def test_invalid_values_fail_closed(self):
        for value in (None,True,"NaN","Infinity","-4","hi"):
            with self.subTest(value=value),self.assertRaises(VenueError):
                _number(value,positive=True)

    def test_market_identity_venue_specific(self):
        self.store.register([Market("coinbase","BTC-USD","BTC","USD"),
                             Market("kraken","XXBTZUSD","XBT","USD")],100)
        self.assertEqual(len(self.store.markets("coinbase")),1)
        self.assertEqual(len(self.store.markets("kraken")),1)

    def test_poll_stores_deterministically(self):
        def fetch(venue,path):
            return COINBASE if path=="/products" else TICKER_CB
        result=poll_once("coinbase",self.store,["BTC-USD"],fetch,lambda:100,lambda t:None)
        self.assertEqual(result["status"],"ok")
        self.assertEqual(self.store.markets("coinbase")[0]["last_price"],"100123.4500")
        self.assertEqual(len(self.store.history("coinbase","BTC-USD")),1)

    def test_duplicate_snapshot_idempotent(self):
        m=Market("coinbase","BTC-USD","BTC","USD")
        self.store.register([m],99)
        s=get_snapshot(m,lambda *_:TICKER_CB,lambda:100)
        self.store.record(s)
        self.store.record(s)
        self.assertEqual(len(self.store.history("coinbase","BTC-USD")),1)

    def test_failed_ticker_not_fake_price(self):
        result=poll_once("coinbase",self.store,["BTC-USD"],
                         lambda v,p:COINBASE if p=="/products" else {},
                         lambda:100,lambda t:None)
        self.assertEqual(result["status"],"unavailable")
        self.assertEqual(self.store.history("coinbase","BTC-USD"),[])

    def test_failed_market_returns_status(self):
        result=poll_once("coinbase",self.store,["FAKE-USD"],
                         lambda *_:COINBASE,lambda:100)
        self.assertEqual(result["status"],"unavailable")

    def test_health_retains_last_success(self):
        self.store.health("coinbase","ok",100)
        self.store.health("coinbase","unavailable",101,"rate limit")
        x=self.store.sources()[0]
        self.assertEqual(x["last_success"],100)
        self.assertEqual(x["status"],"unavailable")

    def test_registration_required_for_prices(self):
        m=Market("coinbase","BTC-USD","BTC","USD")
        with self.assertRaises(VenueError):
            self.store.record(get_snapshot(m,lambda *_:TICKER_CB,lambda:1))

    def test_path_validation(self):
        for bad in ("http://evil","../secret","ABC?x=y"):
            with self.assertRaises(VenueError): _safe_id(bad)

    def test_api_sources(self):
        code,body=handle_get("/api/venues/sources",self.store)
        self.assertEqual(code,200)
        self.assertFalse(body["live_probed"])

    def test_api_markets_empty_without_unsupported_claims(self):
        code,body=handle_get("/api/venues/markets?venue=kraken",self.store)
        self.assertEqual(code,200)
        self.assertEqual(body["markets"],[])
        self.assertEqual(body["coverage"],"sampled-and-limited")

    def test_api_history_is_not_ohlcv(self):
        code,body=handle_get("/api/venues/history?venue=coinbase&market=BTC-USD",self.store)
        self.assertEqual(code,200)
        self.assertEqual(body["series_type"],"sampled_last_trade_price")

    def test_api_rejects_invalid_queries(self):
        for path in ("/api/venues/markets?venue=none",
                     "/api/venues/markets?venue=kraken&limit=0",
                     "/api/venues/history?venue=kraken&market=../secret",
                     "/api/venues/sources?unexpected=1"):
            with self.subTest(path=path):
                self.assertEqual(handle_get(path,self.store)[0],400)

    def test_api_does_not_steal_existing_routes(self):
        self.assertIsNone(handle_get("/api/health",self.store))

if __name__=="__main__":
    unittest.main()
