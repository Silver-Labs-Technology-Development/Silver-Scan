"""Offline pool comparison and CoinMarketCap exchange-map tests.

All sample observations are synthetic TEST DATA: they are not shown on the site
and are never shipped as production market facts.
"""
import json
import time
from unittest.mock import patch

import pytest

from app import coverage as C
from app import pool_market as P


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv("SILVERSCAN_POOL_DATA_AUTHORIZED",raising=False)
    monkeypatch.delenv("SILVERSCAN_POOL_DATA_PATH",raising=False)
    C._CACHE.clear()
    yield
    C._CACHE.clear()


def test_disabled_import_exposes_no_fictitious_pool_directory():
    result=P.directory("all")
    assert result["provider_data_loaded"] is False
    assert result["pools"]==[]
    assert result["total_matching"]==0
    assert result["fetched_at"] is None
    assert "not configured" in result["warning"]


def _source(tmp_path,monkeypatch,minutes_ago=2):
    now=int(time.time())-minutes_ago*60
    # Example coin ID is intentionally synthetic and should not be publicly
    # treated as a mineable or registered market asset.
    dataset={
        "schema_version":1,
        "provider":"MiningPoolStats",
        "permission_reference":"Permission confirmed separately by operator",
        "fetched_at":now,
        "networks":[{"coin":"synthetic-test-chain",
                     "coingecko_id":"synthetic-test-coin",
                     "algorithm":"SHA-256d",
                     "network_hashrate_hps":1e12,
                     "difficulty":100.0,
                     "block_reward":25.0,
                     "blocks_per_day":144.0,
                     "observed_at":now}],
        "pools":[
            {"coin":"synthetic-test-chain","pool_id":"pool-a","name":"Test A",
             "url":"https://example.org/pool-a",
             "source_url":"https://miningpoolstats.stream/test-source",
             "payout_method":"PPLNS","fee_percent":1.5,
             "pool_hashrate_hps":1e11,"miners":30,
             "minimum_payout":0.05,"observed_at":now,"status":"online"},
            {"coin":"synthetic-test-chain","pool_id":"pool-b","name":"Test B",
             "url":"https://example.org/pool-b",
             "payout_method":"PPS","fee_percent":3.0,
             "pool_hashrate_hps":2e11,"miners":40,
             "observed_at":now,"status":"online"},
            {"coin":"synthetic-test-chain","pool_id":"pool-c","name":"Offline C",
             "url":"javascript:alert(1)",
             "payout_method":"UNKNOWN","fee_percent":None,
             "pool_hashrate_hps":None,"observed_at":None,"status":"offline"},
        ],
    }
    file=tmp_path/"permissioned_pool_dataset.json"
    file.write_text(json.dumps(dataset),encoding="utf-8")
    monkeypatch.setenv("SILVERSCAN_POOL_DATA_PATH",str(file))
    monkeypatch.setenv("SILVERSCAN_POOL_DATA_AUTHORIZED","1")
    return file,now


def test_permission_gate_import_scoring_and_normalized_coin_identity(tmp_path,monkeypatch):
    _source(tmp_path,monkeypatch)
    result=P.directory("synthetic-test-chain",sort="score",limit=2,offset=0)
    assert result["provider_data_loaded"] is True
    assert result["provider_permission_asserted"] is True
    assert result["total_matching"]==3
    assert len(result["pools"])==2
    assert len(result["networks"])==1
    assert result["networks"][0]["coingecko_id"]=="synthetic-test-coin"
    assert result["networks"][0]["network_hashrate_hps"]==1e12
    assert result["pools"][0]["preference_score"] is not None
    assert result["pools"][1]["preference_score"] is not None
    assert result["pools"][0]["preference_score"]>=result["pools"][1]["preference_score"]
    assert result["pools"][0]["network_share_pct"]>0
    final=P.directory("synthetic-test-chain",sort="fee",limit=10)
    assert final["pools"][-1]["preference_score"] is None
    assert final["pools"][-1]["url"] is None
    assert final["pools"][-1]["fee_percent"] is None
    assert final["pools"][-1]["status"]=="offline"


def test_file_requires_explicit_permission_and_safe_timestamps(tmp_path,monkeypatch):
    file,now=_source(tmp_path,monkeypatch,minutes_ago=10080+5)
    result=P.directory()
    assert result["pools"]==[]
    assert "too old" in result["warning"]
    # Invalid record cannot claim a license by only changing the env var.
    file.write_text(json.dumps({"schema_version":1,"provider":"MiningPoolStats",
                                "permission_reference":"","fetched_at":now,
                                "pools":[],"networks":[]}))
    again=P.directory()
    assert again["provider_data_loaded"] is False
    assert "permission" in again["warning"]


@pytest.mark.parametrize("input", ["<script>","../etc/passwd","coingecko:btc"])
def test_bad_coin_filter_is_rejected(input):
    with pytest.raises(ValueError):
        P.directory(input)


def test_cmc_exchange_keyless_map_keeps_separate_provider_ids(monkeypatch):
    monkeypatch.delenv("CMC_API_KEY",raising=False)
    raw={"status":{"error_code":0},"data":[
        {"id":270,"name":"Example Exchange","slug":"example-exchange",
         "is_active":1,"status":"active","is_redistributable":0},
        {"id":271,"name":"Other Venue","slug":"other",
         "is_active":0,"status":"untracked","is_redistributable":0},
    ]}
    with patch.object(C,"_fetch",return_value=raw) as fetch:
        result=C.cmc_exchange_map(2,30)
    assert result["source"]=="CoinMarketCap /v1/exchange/map"
    assert result["exchanges"][0]["id"]=="coinmarketcap:270"
    assert result["exchanges"][0]["rank"] is None
    assert result["exchanges"][0]["volume_24h_btc"] is None
    assert result["exchanges"][0]["trust_score"] is None
    assert result["exchanges"][0]["is_redistributable"] is False
    assert result["exchanges"][1]["tracked"] is False
    assert "/public-api/v1/exchange/map" in fetch.call_args.args[0]
    assert "start=31" in fetch.call_args.args[0]
