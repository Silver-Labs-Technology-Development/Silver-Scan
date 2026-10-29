"""No external APIs: fixtures model venue_observations' SQLite schema."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.market_insights import InsightStore, handle_get


class InsightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/"venues.db"
        with sqlite3.connect(self.path) as db:
            db.executescript("""
            CREATE TABLE venue_markets(venue TEXT NOT NULL,market_id TEXT NOT NULL,
              base TEXT NOT NULL,quote TEXT NOT NULL,first_seen INTEGER NOT NULL,
              last_seen INTEGER NOT NULL,PRIMARY KEY(venue,market_id));
            CREATE TABLE venue_snapshots(venue TEXT NOT NULL,market_id TEXT NOT NULL,
              observed_at INTEGER NOT NULL,last_price TEXT NOT NULL,
              volume_24h_base TEXT,volume_24h_quote_estimate TEXT,
              quote_estimate_method TEXT,source_time INTEGER,source TEXT NOT NULL,
              PRIMARY KEY(venue,market_id,observed_at));
            CREATE TABLE venue_health(venue TEXT PRIMARY KEY,status TEXT NOT NULL,
              last_attempt INTEGER,last_success INTEGER,last_error TEXT);
            """)
            db.executemany("INSERT INTO venue_markets VALUES(?,?,?,?,1,1)",[
                ("coinbase","BTC-USD","BTC","USD"),
                ("coinbase","ETH-USD","ETH","USD"),
                ("kraken","XXBTZUSD","XBT","USD"),
            ])
            points=[("coinbase","BTC-USD",100000,"100"),
                    ("coinbase","BTC-USD",103600,"120"),
                    ("coinbase","ETH-USD",100000,"200"),
                    ("coinbase","ETH-USD",103600,"150"),
                    ("kraken","XXBTZUSD",103595,"123")]
            db.executemany("INSERT INTO venue_snapshots VALUES(?,?,?,?,NULL,NULL,NULL,NULL,'fixture')",
                           points)
            db.execute("INSERT INTO venue_health VALUES('coinbase','ok',103600,103600,NULL)")
        self.store=InsightStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_movers_use_two_observed_samples_and_price_units(self):
        data=self.store.movers("coinbase","1h",10,103600)
        self.assertEqual(data["pairs_with_comparable_history"],2)
        self.assertEqual([x["market_id"] for x in data["gainers"]],["BTC-USD"])
        self.assertEqual(data["gainers"][0]["change_pct"],"20.0000")
        self.assertEqual(data["losers"][0]["change_pct"],"-25.0000")
        self.assertFalse(data["gainers"][0]["asset_identity_verified"])

    def test_movers_hide_old_or_single_snapshot(self):
        self.assertEqual(self.store.movers("coinbase","1h",as_of=104000)["gainers"],[])
        self.assertEqual(self.store.movers("kraken","1h",as_of=103600)["gainers"],[])

    def test_quality_never_claims_full_coverage(self):
        result=self.store.quality(as_of=103600)
        cb=result["sources"][0]
        self.assertEqual(cb["directory_pairs"],2)
        self.assertEqual(cb["sampled_pairs"],2)
        self.assertEqual(cb["fresh_pairs"],2)
        self.assertEqual(result["coverage"],"sampled exchange markets only")
        self.assertFalse(result["live_probed"])
        self.assertEqual(result["sources"][1]["last_collection_status"],"never_polled")

    def test_comparison_requires_explicit_operator_mapping(self):
        empty=self.store.cross_venue("native:bitcoin","fiat:USD",103600)
        self.assertIsNone(empty["highest_vs_lowest_pct"])
        self.assertEqual(empty["status"],"insufficient_comparable_markets")
        with self.assertRaises(ValueError):
            self.store.review_mapping("kraken","XXBTZUSD","native:bitcoin","fiat:USD","http://not-https.example")
        self.store.review_mapping("coinbase","BTC-USD","native:bitcoin","fiat:USD",
                                  "https://www.coinbase.com/",at=103600)
        self.store.review_mapping("kraken","XXBTZUSD","native:bitcoin","fiat:USD",
                                  "https://www.kraken.com/",at=103600)
        self.assertEqual(self.store.cross_venue("native:bitcoin","fiat:USD",103600)["highest_vs_lowest_pct"],"2.5000")
        self.assertEqual(self.store.cross_venue("native:bitcoin","fiat:USD",103600)["status"],"comparable")
        self.assertEqual(len(self.store.cross_venue("native:bitcoin","fiat:USD",104000)["observed_venues"]),0)

    def test_skew_blocks_comparison_even_with_fresh_observations(self):
        self.store.review_mapping("coinbase","BTC-USD","native:bitcoin","fiat:USD","https://www.coinbase.com/")
        self.store.review_mapping("kraken","XXBTZUSD","native:bitcoin","fiat:USD","https://www.kraken.com/")
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE venue_snapshots SET observed_at=103350 WHERE venue='kraken'")
        result=self.store.cross_venue("native:bitcoin","fiat:USD",103600)
        self.assertEqual(result["status"],"insufficient_comparable_markets")
        self.assertIsNone(result["highest_vs_lowest_pct"])

    def test_never_map_nonexistent_pairs_or_unknown_assets(self):
        with self.assertRaises(ValueError):
            self.store.review_mapping("coinbase","FAKE-USD","native:bitcoin","fiat:USD","https://example.org/")
        with self.assertRaises(ValueError):
            self.store.review_mapping("coinbase","BTC-USD","BTC","fiat:USD","https://example.org/")

    def test_http_adapter_rejects_invalid_or_unrelated_routes(self):
        self.assertIsNone(handle_get("/api/accounts",self.store))
        for path in ("/api/insights/local/movers?venue=coinbase&window=100d",
                     "/api/insights/local/movers?venue=coinbase&limit=1000",
                     "/api/insights/local/movers?venue=kraken&venue=coinbase",
                     "/api/insights/local/quality?secret=1",
                     "/api/insights/local/compare?base_asset=BTC&quote_asset=USD"):
            code,resp=handle_get(path,self.store)
            self.assertEqual(code,400,path)
            self.assertIn("error",resp)
        code,resp=handle_get("/api/insights/local/quality",self.store)
        self.assertEqual(code,200)
        self.assertIn("sources",resp)

    def test_bad_database_returns_unavailable_not_fake_data(self):
        empty=InsightStore(Path(self.temp.name)/"empty.sqlite")
        code,resp=handle_get("/api/insights/local/quality",empty)
        self.assertEqual(code,503)
        self.assertEqual(resp["error"],"Local observation database unavailable")


if __name__=="__main__":
    unittest.main()
