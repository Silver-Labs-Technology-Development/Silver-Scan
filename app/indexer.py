import sqlite3, os, json
from app import rpc, config

DB_PATH = os.environ.get("SILVERSCAN_DB", "silverscan.db")

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS blocks (height INTEGER PRIMARY KEY, hash TEXT UNIQUE, prevhash TEXT);
    CREATE TABLE IF NOT EXISTS txs (txid TEXT PRIMARY KEY, block_height INTEGER, block_hash TEXT);
    CREATE TABLE IF NOT EXISTS outputs (txid TEXT, n INTEGER, value REAL, address TEXT, spent_by TEXT, PRIMARY KEY(txid,n));
    CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
    """)
    c.commit()
    c.close()

def get_tip():
    c = conn()
    r = c.execute("SELECT MAX(height) as h FROM blocks").fetchone()
    c.close()
    return r["h"] if r and r["h"] is not None else -1

def index_block(height):
    c = conn()
    # idempotent: skip if present
    exists = c.execute("SELECT 1 FROM blocks WHERE height=?", (height,)).fetchone()
    if exists:
        c.close()
        return False
    bh = rpc.call(config.BTCS_RPC_URL, config.BTCS_RPC_USER, config.BTCS_RPC_PASSWORD, "getblockhash", [height])
    blk = rpc.call(config.BTCS_RPC_URL, config.BTCS_RPC_USER, config.BTCS_RPC_PASSWORD, "getblock", [bh, 2])
    # parent check
    if height > 0:
        prev = c.execute("SELECT hash FROM blocks WHERE height=?", (height-1,)).fetchone()
        if prev and blk.get("previousblockhash") and prev["hash"] != blk["previousblockhash"]:
            # reorg: remove from height onward
            c.execute("DELETE FROM blocks WHERE height>=?", (height,))
            c.execute("DELETE FROM txs WHERE block_height>=?", (height,))
            # rebuild outputs spent flags for affected? simplify: keep
            c.commit()
    c.execute("INSERT INTO blocks(height,hash,prevhash) VALUES(?,?,?)", (height, bh, blk.get("previousblockhash")))
    for t in blk.get("tx", []):
        if not isinstance(t, dict): continue
        c.execute("INSERT OR IGNORE INTO txs(txid,block_height,block_hash) VALUES(?,?,?)", (t["txid"], height, bh))
        for v in t.get("vout", []):
            spk = v.get("scriptPubKey", {})
            addr = spk.get("address")
            c.execute("INSERT OR IGNORE INTO outputs(txid,n,value,address,spent_by) VALUES(?,?,?,?,?)",
                      (t["txid"], v["n"], v.get("value",0), addr, None))
        for vin in t.get("vin", []):
            if "txid" in vin:
                c.execute("UPDATE outputs SET spent_by=? WHERE txid=? AND n=?", (t["txid"], vin["txid"], vin.get("vout")))
    c.commit()
    c.close()
    return True

def sync_to_tip(max_blocks=1000):
    info = rpc.call(config.BTCS_RPC_URL, config.BTCS_RPC_USER, config.BTCS_RPC_PASSWORD, "getblockchaininfo")
    tip = info["blocks"]
    cur = get_tip()
    start = cur + 1 if cur >= 0 else 0
    for h in range(start, tip+1):
        index_block(h)
    return tip

def address_balance(address):
    c = conn()
    # sum outputs to address not spent
    rows = c.execute("SELECT value FROM outputs WHERE address=? AND spent_by IS NULL", (address,)).fetchall()
    bal = sum(r["value"] or 0 for r in rows)
    txs = c.execute("""SELECT DISTINCT t.txid, t.block_height FROM txs t
        JOIN outputs o ON o.txid=t.txid WHERE o.address=?""", (address,)).fetchall()
    c.close()
    return {"address": address, "balance": bal, "txCount": len(txs),
            "transactions": [{"txid": r["txid"], "height": r["block_height"]} for r in txs]}
