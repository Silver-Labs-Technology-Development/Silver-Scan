"""Deterministic canonicality, satoshi and bounded backfill regression tests."""
from __future__ import annotations

import sqlite3

import pytest

from app import indexer as I


def tx(txid, outputs, inputs=None):
    return {
        "txid": txid,
        "vin": inputs if inputs is not None else [{"coinbase": "00"}],
        "vout": [
            {"n": n, "value": value, "scriptPubKey": {"address": address}}
            for n, (address, value) in enumerate(outputs)
        ],
    }


def block(height, block_hash, prev_hash, transactions):
    return {
        "height": height, "hash": block_hash, "previousblockhash": prev_hash,
        "time": 1700000000 + height, "tx": transactions,
    }


@pytest.fixture
def fixture_node(tmp_path, monkeypatch):
    monkeypatch.setattr(I, "DB_PATH", str(tmp_path / "silver-index.sqlite3"))
    b0 = block(0, "0" * 64, None, [tx("genesis", [("addrA", 50.0)])])
    b1 = block(1, "1" * 64, b0["hash"], [
        tx("spend1", [("addrB", 20.00000001), ("addrA", 29.99999999)],
           [{"txid": "genesis", "vout": 0}]),
    ])
    b2 = block(2, "2" * 64, b1["hash"], [
        tx("spend2", [("addrC", 20.00000001)],
           [{"txid": "spend1", "vout": 0}]),
    ])
    chain = [b0, b1, b2]

    def respond(method, params=None):
        if method == "getblockchaininfo":
            return {"blocks": len(chain) - 1}
        if method == "getblockhash":
            return chain[params[0]]["hash"]
        if method == "getblock":
            return next(b for b in chain if b["hash"] == params[0])
        raise AssertionError("Unexpected RPC method " + method)

    monkeypatch.setattr(I, "_rpc", respond)
    I.init_db()
    return chain


def test_genesis_backfill_is_bounded_and_exact(fixture_node):
    assert I.get_tip() == -1
    first = I.sync_to_tip(1)
    assert first == {"indexed_tip": 0, "node_height_at_start": 2, "processed_blocks": 1, "caught_up": False}
    assert I.address_balance("addrA")["balance_sats"] == 5_000_000_000
    second = I.sync_to_tip(2)
    assert second["caught_up"] is True
    assert I.get_tip() == 2
    assert I.address_balance("addrA")["balance_sats"] == 2_999_999_999
    assert I.address_balance("addrB")["balance_sats"] == 0
    assert I.address_balance("addrC")["balance_sats"] == 2_000_000_001
    history = I.address_balance("addrB")
    assert history["txCount"] == 2  # receive + spend
    assert {x["txid"] for x in history["transactions"]} == {"spend1", "spend2"}
    assert I.sync_to_tip(1)["processed_blocks"] == 0
    assert I.index_block(2) is False


def test_reorganization_reverses_orphan_spends_and_value(fixture_node):
    I.sync_to_tip(10)
    chain = fixture_node
    b1 = block(1, "a" * 64, chain[0]["hash"], [
        tx("replacement1", [("addrD", 50)], [{"txid": "genesis", "vout": 0}])
    ])
    b2 = block(2, "b" * 64, b1["hash"], [
        tx("replacement2", [("addrE", 50)], [{"txid": "replacement1", "vout": 0}])
    ])
    chain[1:] = [b1, b2]
    result = I.sync_to_tip(10)
    assert result["processed_blocks"] == 2
    assert result["caught_up"] is True
    assert I.address_balance("addrC")["balance_sats"] == 0
    assert I.address_balance("addrB")["txCount"] == 0
    assert I.address_balance("addrE")["balance_sats"] == 5_000_000_000
    with I.conn() as db:
        orphan = db.execute("SELECT COUNT(*) FROM chain_txs WHERE txid='spend2'").fetchone()[0]
    assert orphan == 0


def test_shrunk_node_tip_rolls_back_index(fixture_node):
    I.sync_to_tip(10)
    fixture_node.pop()
    result = I.sync_to_tip(10)
    assert result["indexed_tip"] == 1
    assert result["processed_blocks"] == 0
    assert I.address_balance("addrB")["balance_sats"] == 2_000_000_001


def test_rejects_fractional_or_invalid_satoshis():
    for invalid in ("0.000000001", "-1", "nan", "inf", None):
        with pytest.raises(ValueError):
            I._satoshis(invalid)
    assert I._satoshis("0.00000001") == 1
    assert I._satoshis(0.1) == 10_000_000


def test_validation_and_contiguous_requirement(fixture_node):
    for max_blocks in (0, -1, 1001, 2.0, True):
        with pytest.raises(ValueError):
            I.sync_to_tip(max_blocks)
    with pytest.raises(ValueError, match="genesis"):
        I.index_block(2)
    for limit, offset in ((0, 0), (101, 0), (1, -1), (1, 100001)):
        with pytest.raises(ValueError):
            I.address_balance("addrA", limit, offset)


def test_legacy_float_tables_are_not_used_as_accurate_balances(fixture_node):
    with sqlite3.connect(I.DB_PATH) as db:
        db.execute("CREATE TABLE outputs(txid TEXT,n INTEGER,value REAL,address TEXT,spent_by TEXT)")
        db.execute("INSERT INTO outputs VALUES('old',0,9999,'addrA',NULL)")
    assert I.address_balance("addrA")["balance_sats"] == 0
    I.sync_to_tip(1)
    assert I.address_balance("addrA")["balance_sats"] == 5_000_000_000


def test_failure_before_commit_preserves_tip(fixture_node):
    fixture_node[1]["tx"][0]["vout"][0]["value"] = 0.000000001
    I.sync_to_tip(1)
    with pytest.raises(ValueError):
        I.sync_to_tip(5)
    assert I.get_tip() == 0
