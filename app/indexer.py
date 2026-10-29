"""BTCS L1 experimental indexer.

Read-only wrt the chain. Stores satoshis as INTEGER; preserves old prototype
tables without trusting their REAL balances. All canonical block writes and
rollbacks are atomic. Does not independently verify Bitcoin consensus.
Run with: python -m app.indexer --max-blocks 100
"""
from __future__ import annotations

import argparse
from contextlib import closing
from decimal import Decimal, InvalidOperation
import os
import sqlite3
from pathlib import Path

from app import config, rpc

DB_PATH = os.environ.get("SILVERSCAN_DB", "silverscan.db")
SATOSHI = Decimal("100000000")


def conn():
    database = sqlite3.connect(DB_PATH, timeout=10)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys=ON")
    database.execute("PRAGMA busy_timeout=10000")
    return database


def init_db():
    """Create a new exact-value index, not an unsafe REAL-to-int migration.

    Old prototype blocks/txs/outputs remain untouched and are intentionally
    excluded from balances, until a deliberate reindex from genesis completes.
    """
    with closing(conn()) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS chain_blocks (
            height INTEGER PRIMARY KEY,
            hash TEXT NOT NULL UNIQUE,
            prevhash TEXT,
            time INTEGER
        );
        CREATE TABLE IF NOT EXISTS chain_txs (
            txid TEXT PRIMARY KEY,
            block_height INTEGER NOT NULL REFERENCES chain_blocks(height) ON DELETE CASCADE,
            block_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chain_outputs (
            txid TEXT NOT NULL REFERENCES chain_txs(txid) ON DELETE CASCADE,
            n INTEGER NOT NULL,
            value_sats INTEGER NOT NULL CHECK(value_sats >= 0),
            address TEXT,
            spent_by TEXT,
            PRIMARY KEY(txid,n)
        );
        CREATE TABLE IF NOT EXISTS chain_inputs (
            txid TEXT NOT NULL REFERENCES chain_txs(txid) ON DELETE CASCADE,
            vin_index INTEGER NOT NULL,
            prev_txid TEXT NOT NULL,
            prev_n INTEGER NOT NULL,
            PRIMARY KEY(txid,vin_index)
        );
        CREATE INDEX IF NOT EXISTS idx_chain_outputs_address ON chain_outputs(address);
        CREATE INDEX IF NOT EXISTS idx_chain_inputs_outpoint ON chain_inputs(prev_txid,prev_n);
        CREATE INDEX IF NOT EXISTS idx_chain_txs_height ON chain_txs(block_height);
        """)


def _rpc(method, params=None):
    return rpc.call(config.BTCS_RPC_URL, config.BTCS_RPC_USER,
                    config.BTCS_RPC_PASSWORD, method, params or [])


def _satoshis(value):
    """Fail rather than round off-chain values silently."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid output value") from exc
    sats = number * SATOSHI
    if not sats.is_finite() or sats < 0 or sats != sats.to_integral_value():
        raise ValueError("output value must be a nonnegative whole satoshi")
    if sats >= 2**63:
        raise ValueError("output value exceeds SQLite integer range")
    return int(sats)


def get_tip():
    with closing(conn()) as db:
        result = db.execute("SELECT MAX(height) FROM chain_blocks").fetchone()[0]
    return result if result is not None else -1


def get_tip_info():
    with closing(conn()) as db:
        row = db.execute(
            "SELECT height,hash,time FROM chain_blocks ORDER BY height DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row is not None else None


def _rollback_from(db, height):
    """Reverse every spend made by an orphan and remove orphan descendants."""
    db.execute(
        """UPDATE chain_outputs SET spent_by=NULL
           WHERE spent_by IN (SELECT txid FROM chain_txs WHERE block_height>=?)""",
        (height,),
    )
    db.execute("DELETE FROM chain_blocks WHERE height>=?", (height,))


def _canonical_tip():
    """Reconcile indexed hashes with the active node, back to common ancestor."""
    try:
        node_height = int(_rpc("getblockchaininfo")["blocks"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("node did not return a chain height") from exc
    if node_height < 0:
        raise ValueError("invalid node chain height")
    with closing(conn()) as db:
        rows = db.execute("SELECT height,hash FROM chain_blocks ORDER BY height DESC").fetchall()
        divergent_height = None
        for row in rows:
            height = row["height"]
            if height > node_height or _rpc("getblockhash", [height]) != row["hash"]:
                divergent_height = height
            else:
                break
        if divergent_height is not None:
            with db:
                _rollback_from(db, divergent_height)
    return node_height


def index_block(height):
    """Index only the next block, preserving a contiguous, canonical prefix."""
    if type(height) is not int or height < 0:
        raise ValueError("height must be a nonnegative integer")
    expected_hash = _rpc("getblockhash", [height])
    block = _rpc("getblock", [expected_hash, 2])
    if not isinstance(block, dict) or block.get("hash") != expected_hash or block.get("height") != height:
        raise ValueError("node block/hash response disagrees with height")
    transactions = block.get("tx")
    if not isinstance(transactions, list):
        raise ValueError("node returned no transaction array")

    # Validate transaction values before opening a write transaction.
    parsed = []
    for transaction in transactions:
        if not isinstance(transaction, dict) or not isinstance(transaction.get("txid"), str):
            raise ValueError("invalid transaction")
        outputs = []
        for output in transaction.get("vout", []):
            script = output.get("scriptPubKey") or {}
            address = script.get("address")
            if address is None and isinstance(script.get("addresses"), list) and len(script["addresses"]) == 1:
                address = script["addresses"][0]
            if address is not None and not isinstance(address, str):
                raise ValueError("invalid output address")
            outputs.append((int(output["n"]), _satoshis(output["value"]), address))
        inputs = []
        for position, entry in enumerate(transaction.get("vin", [])):
            if "txid" in entry:
                inputs.append((position, str(entry["txid"]), int(entry["vout"])))
        parsed.append((transaction["txid"], outputs, inputs))

    with closing(conn()) as db:
        with db:
            last = db.execute(
                "SELECT height,hash FROM chain_blocks ORDER BY height DESC LIMIT 1"
            ).fetchone()
            if last is not None and height <= last["height"]:
                recorded = db.execute("SELECT hash FROM chain_blocks WHERE height=?", (height,)).fetchone()
                if recorded and recorded["hash"] == expected_hash:
                    return False
                _rollback_from(db, height)
                last = db.execute(
                    "SELECT height,hash FROM chain_blocks ORDER BY height DESC LIMIT 1"
                ).fetchone()
            if height != (last["height"] + 1 if last else 0):
                raise ValueError("index must start at genesis and advance one height at a time")
            if last and block.get("previousblockhash") != last["hash"]:
                raise ValueError("block parent disagrees with indexed canonical tip")
            db.execute(
                "INSERT INTO chain_blocks(height,hash,prevhash,time) VALUES(?,?,?,?)",
                (height, expected_hash, block.get("previousblockhash"), block.get("time")),
            )
            for txid, outputs, inputs in parsed:
                db.execute(
                    "INSERT INTO chain_txs(txid,block_height,block_hash) VALUES(?,?,?)",
                    (txid, height, expected_hash),
                )
                for n, value, address in outputs:
                    db.execute(
                        "INSERT INTO chain_outputs(txid,n,value_sats,address,spent_by) VALUES(?,?,?,?,NULL)",
                        (txid, n, value, address),
                    )
                for position, prev_txid, prev_n in inputs:
                    db.execute(
                        "INSERT INTO chain_inputs(txid,vin_index,prev_txid,prev_n) VALUES(?,?,?,?)",
                        (txid, position, prev_txid, prev_n),
                    )
                    # A referenced output may not exist if history was not indexed.
                    # Since we require a genesis-first prefix, normally it exists.
                    db.execute(
                        "UPDATE chain_outputs SET spent_by=? WHERE txid=? AND n=? AND spent_by IS NULL",
                        (txid, prev_txid, prev_n),
                    )
    return True


def sync_to_tip(max_blocks=100):
    """Sync a bounded batch, never unbounded chain data from a web request."""
    if type(max_blocks) is not int or not 1 <= max_blocks <= 1000:
        raise ValueError("max_blocks must be an integer from 1 to 1000")
    init_db()
    node_height = _canonical_tip()
    start = get_tip() + 1
    processed = 0
    for height in range(start, min(node_height + 1, start + max_blocks)):
        index_block(height)
        processed += 1
    return {
        "indexed_tip": get_tip(),
        "node_height_at_start": node_height,
        "processed_blocks": processed,
        "caught_up": get_tip() == node_height,
    }


def address_balance(address, limit=50, offset=0):
    if not isinstance(address, str) or not address or len(address) > 128:
        raise ValueError("invalid address")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    if type(offset) is not int or not 0 <= offset <= 100000:
        raise ValueError("offset must be 0..100000")
    with closing(conn()) as db:
        total = db.execute(
            "SELECT COALESCE(SUM(value_sats),0) FROM chain_outputs WHERE address=? AND spent_by IS NULL",
            (address,),
        ).fetchone()[0]
        tx_query = """
        SELECT txid,block_height FROM chain_txs
        WHERE txid IN (SELECT txid FROM chain_outputs WHERE address=?)
           OR txid IN (
              SELECT i.txid FROM chain_inputs i
              JOIN chain_outputs o ON o.txid=i.prev_txid AND o.n=i.prev_n
              WHERE o.address=?
           )
        """
        count = db.execute("SELECT COUNT(*) FROM (" + tx_query + ")", (address, address)).fetchone()[0]
        rows = db.execute(
            tx_query + " ORDER BY block_height DESC,txid LIMIT ? OFFSET ?",
            (address, address, limit, offset),
        ).fetchall()
        tip = db.execute("SELECT MAX(height) FROM chain_blocks").fetchone()[0]
    return {
        "address": address,
        "balance_sats": total,
        "balance": str(Decimal(total) / SATOSHI),
        "txCount": count,
        "transactions": [dict(row) | {"height": row["block_height"]} for row in rows],
        "indexedTip": -1 if tip is None else tip,
        "indexComplete": False,  # unknown until node tip has been checked
        "offset": offset,
        "limit": limit,
        "note": "Indexed confirmed-chain subset only; check index status and node sync before treating this as complete.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Silver Scan bounded BTCS L1 indexer")
    parser.add_argument("--max-blocks", type=int, default=100)
    args = parser.parse_args(argv)
    print(sync_to_tip(args.max_blocks))


if __name__ == "__main__":
    main()
