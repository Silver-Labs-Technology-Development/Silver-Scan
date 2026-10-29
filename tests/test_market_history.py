"""Offline coverage for market sample history and honest heatmap calculations."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.market_history import HistoryStore, handle_get


class MarketHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "venue.db"
        with sqlite3.connect(self.path) as db:
            db.executescript("""
            CREATE TABLE venue_markets(
              venue TEXT NOT NULL, market_id TEXT NOT NULL,
              base TEXT NOT NULL, quote TEXT NOT NULL,
              first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
              PRIMARY KEY(venue, market_id));
            CREATE TABLE venue_snapshots(
              venue TEXT NOT NULL, market_id TEXT NOT NULL, observed_at INTEGER NOT NULL,
              last_price TEXT NOT NULL, volume_24h_base TEXT,
              volume_24h_quote_estimate TEXT, quote_estimate_method TEXT,
              source_time INTEGER, source TEXT NOT NULL,
              PRIMARY KEY(venue, market_id, observed_at));
            """)
            db.executemany("INSERT INTO venue_markets VALUES(?,?,?,?,1,1)", [
                ("coinbase", "BTC-USD", "BTC", "USD"),
                ("coinbase", "ETH-USD", "ETH", "USD"),
                ("coinbase", "SOL-USD", "SOL", "USD"),
                ("coinbase", "STALE-USD", "STALE", "USD"),
                ("coinbase", "EMPTY-USD", "EMPTY", "USD"),
                ("coinbase", "BTC-USDT", "BTC", "USDT"),
                ("kraken", "XXBTZUSD", "XBT", "USD"),
            ])
            samples = [
                ("coinbase", "BTC-USD", 196400, "100"),
                ("coinbase", "BTC-USD", 199980, "120"),
                ("coinbase", "BTC-USD", 200000, "130.000000000000000001"),
                ("coinbase", "ETH-USD", 196400, "200"),
                ("coinbase", "ETH-USD", 200000, "150"),
                ("coinbase", "SOL-USD", 196400, "100"),
                ("coinbase", "SOL-USD", 200000, "100"),
                ("coinbase", "STALE-USD", 196400, "50"),
                ("coinbase", "STALE-USD", 199000, "80"),
                ("coinbase", "BTC-USDT", 196400, "90"),
                ("coinbase", "BTC-USDT", 200000, "99"),
                ("kraken", "XXBTZUSD", 196400, "100"),
                ("kraken", "XXBTZUSD", 200000, "125"),
            ]
            db.executemany("""
              INSERT INTO venue_snapshots
              (venue,market_id,observed_at,last_price,volume_24h_base,
               volume_24h_quote_estimate,quote_estimate_method,source_time,source)
              VALUES(?,?,?,?,NULL,NULL,NULL,NULL,'offline fixture')""", samples)
        self.store = HistoryStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_series_uses_true_recorded_sample_times(self):
        result = self.store.series("coinbase", "BTC-USD", "1h", 3, 200000)
        self.assertEqual(result["status"], "sampled")
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["points_returned"], 3)
        self.assertEqual([p["observed_at"] for p in result["points"]],
                         [196400, 199980, 200000])
        self.assertEqual(result["points"][-1]["last_price_in_quote"],
                         "130.000000000000000001")
        self.assertFalse(result["asset_identity_verified"])
        self.assertEqual(result["series_type"], "sampled_last_traded_price")

    def test_bucketed_series_does_not_fabricate_intermediate_history(self):
        result = self.store.series("coinbase", "BTC-USD", "1h", 2, 200000)
        self.assertLessEqual(result["points_returned"], 2)
        self.assertEqual(result["sample_count"], 3)
        self.assertTrue(all(p["observed_at"] in {196400,199980,200000}
                            for p in result["points"]))
        self.assertIn("Missing time intervals are unfilled", result["note"])

    def test_series_returns_clear_missing_and_stale_states(self):
        unknown = self.store.series("coinbase", "NOT-LISTED", "1h", as_of=200000)
        self.assertEqual(unknown["status"], "market_not_in_directory")
        empty = self.store.series("coinbase", "EMPTY-USD", "1h", as_of=200000)
        self.assertEqual(empty["status"], "no_observations")
        stale = self.store.series("coinbase", "STALE-USD", "1h", as_of=200000)
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["last_observation_age_seconds"], 1000)

    def test_heatmap_reports_actual_comparable_venue_pairs(self):
        result = self.store.heatmap("coinbase", "1h", "USD", 100, 200000)
        self.assertEqual(result["status"], "sampled")
        self.assertEqual([x["market_id"] for x in result["cells"]],
                         ["BTC-USD", "SOL-USD", "ETH-USD"])
        self.assertEqual(result["pairs_with_fresh_samples"], 3)
        self.assertEqual(result["cells"][0]["band"], "up-strong")
        self.assertEqual(result["cells"][1]["band"], "flat")
        self.assertEqual(result["cells"][2]["band"], "down-strong")
        self.assertFalse(result["cells"][0]["asset_identity_verified"])
        self.assertEqual(result["size_metric"], None)

    def test_heatmap_quote_separation_prevents_usd_usdt_mixing(self):
        result = self.store.heatmap("coinbase", "1h", "USDT", 10, 200000)
        self.assertEqual([x["market_id"] for x in result["cells"]], ["BTC-USDT"])
        self.assertEqual(result["cells"][0]["change_percent"], "10.0000")

    def test_missing_reference_is_excluded_not_assumed_zero_change(self):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO venue_markets VALUES('coinbase','NEW-USD','NEW','USD',1,1)")
            db.execute("""INSERT INTO venue_snapshots VALUES
              ('coinbase','NEW-USD',200000,'40',NULL,NULL,NULL,NULL,'fixture')""")
        result = self.store.heatmap("coinbase", "1h", "USD", 100, 200000)
        self.assertEqual(result["pairs_missing_comparable_reference"], 1)
        self.assertNotIn("NEW-USD", [x["market_id"] for x in result["cells"]])

    def test_larger_windows_do_not_invent_yearlong_series(self):
        result = self.store.series("coinbase", "BTC-USD", "1y", 10, 200000)
        self.assertEqual(result["sample_count"], 3)
        self.assertLessEqual(result["points_returned"], 3)
        self.assertEqual(result["first_observed_at"], 196400)

    def test_handler_accepts_only_bounded_read_only_routes(self):
        self.assertIsNone(handle_get("/api/pool", self.store))
        code, result = handle_get("/api/insights/local/heatmap?venue=coinbase&window=24h", self.store)
        self.assertEqual(code, 200)
        self.assertEqual(result["metric"], "sampled_pair_price_percent_change")
        for uri in (
            "/api/insights/local/heatmap?venue=coinbase&limit=900",
            "/api/insights/local/heatmap?venue=coinbase&venue=kraken",
            "/api/insights/local/heatmap?venue=kraken&quote=JPY",
            "/api/insights/local/series?venue=coinbase&market=../secret",
            "/api/insights/local/series?venue=coinbase&market=BTC-USD&window=10y",
            "/api/insights/local/series?venue=coinbase&market=BTC-USD&limit=501",
            "/api/insights/local/series?venue=coinbase&market=BTC-USD&admin=yes",
        ):
            code, body = handle_get(uri, self.store)
            self.assertEqual(code, 400, uri)
            self.assertIn("error", body)

    def test_nonexistent_database_does_not_return_fake_data(self):
        store = HistoryStore(Path(self.temp.name) / "does_not_exist.sqlite")
        code, body = handle_get("/api/insights/local/series?venue=coinbase&market=BTC-USD",store)
        self.assertEqual(code, 503)
        self.assertIn("unavailable", body["error"])


if __name__ == "__main__":
    unittest.main()
