from app.config import BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, BTCS_NETWORK
from app import rpc

class Network:
    def __init__(self, id, name, family, capabilities):
        self.id = id; self.name = name; self.family = family; self.capabilities = capabilities
    def to_dict(self):
        return {"id": self.id, "name": self.name, "family": self.family, "capabilities": self.capabilities}

NETWORKS = [
    Network("btcs-regtest", "Bitcoin Silver (regtest)", "utxo", ["blocks","transactions","address","health","stats"]),
    Network("evm-demo", "EVM Demo (mock adapter)", "evm", ["blocks","transactions","address","contracts","tokens","health"]),
]

def get_network(nid):
    for n in NETWORKS:
        if n.id == nid:
            return n
    return None

def btcs_health():
    info = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblockchaininfo")
    return {"chain": info["chain"], "blocks": info["blocks"], "bestBlockHash": info["bestblockhash"],
            "verificationProgress": info["verificationprogress"], "pruned": info["pruned"]}

def btcs_block(height_or_hash):
    try:
        h = int(height_or_hash)
        bh = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblockhash", [h])
    except ValueError:
        bh = height_or_hash
    blk = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblock", [bh, 2])
    return {"hash": blk["hash"], "height": blk["height"], "time": blk.get("time"),
            "txCount": len(blk.get("tx", [])), "txids": [t if isinstance(t,str) else t.get("txid") for t in blk.get("tx", [])][:20],
            "previousblockhash": blk.get("previousblockhash"), "nextblockhash": blk.get("nextblockhash")}

def btcs_tx(txid):
    try:
        t = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getrawtransaction", [txid, True])
        return {"txid": t["txid"], "blockhash": t.get("blockhash"), "confirmations": t.get("confirmations",0),
                "vin": t.get("vin",[]), "vout": t.get("vout",[]), "size": t.get("size")}
    except Exception:
        # fallback: scan recent blocks (regtest may lack txindex)
        info = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblockchaininfo")
        tip = info["blocks"]
        for h in range(tip, max(tip-50, -1), -1):
            bh = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblockhash", [h])
            blk = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblock", [bh, 2])
            for t in blk.get("tx", []):
                if isinstance(t, dict) and t.get("txid") == txid:
                    return {"txid": t["txid"], "blockhash": blk["hash"], "confirmations": tip-h+1,
                            "vin": t.get("vin",[]), "vout": t.get("vout",[]), "size": t.get("size")}
        raise ValueError("transaction not found")

def btcs_recent_blocks(n=5):
    info = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblockchaininfo")
    tip = info["blocks"]
    out = []
    for h in range(tip, max(tip-n, -1), -1):
        bh = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblockhash", [h])
        b = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblock", [bh, 1])
        out.append({"height": b["height"], "hash": b["hash"], "txCount": b["nTx"], "time": b.get("time")})
    return out

# EVM demo adapter (fixture-backed, clearly labeled)
EVM_BLOCKS = {
    1: {"number":1,"hash":"0xabc1","txCount":2,"transactions":["0xtx1","0xtx2"]},
    2: {"number":2,"hash":"0xabc2","txCount":1,"transactions":["0xtx3"]},
}
def evm_health():
    return {"chain":"evm-demo","blocks":2,"status":"fixture (not live)"}
def evm_block(n):
    b = EVM_BLOCKS.get(int(n))
    if not b: raise ValueError("not found")
    return b


def btcs_address(address, depth=200):
    try:
        info = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getaddressinfo", [address])
    except Exception:
        raise ValueError("invalid address")
    if not info.get("address"):
        raise ValueError("invalid address")
    tip_info = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblockchaininfo")
    tip = tip_info["blocks"]
    start = max(0, tip - depth + 1)
    txs = []
    balance = 0.0
    for h in range(tip, start-1, -1):
        bh = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblockhash", [h])
        blk = rpc.call(BTCS_RPC_URL, BTCS_RPC_USER, BTCS_RPC_PASSWORD, "getblock", [bh, 2])
        for t in blk.get("tx", []):
            if not isinstance(t, dict): continue
            for v in t.get("vout", []):
                spk = v.get("scriptPubKey", {})
                if spk.get("address") == address:
                    txs.append({"txid": t["txid"], "height": h, "value": v.get("value"), "direction": "received"})
                    balance += v.get("value", 0)
    return {"address": address, "isvalid": True, "balance": balance,
            "txCount": len(txs), "transactions": txs[:50],
            "scannedBlocks": tip - start + 1, "tip": tip,
            "note": "Derived by scanning recent blocks; not a full historical index."}
