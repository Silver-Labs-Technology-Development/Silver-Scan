import os
os.environ.setdefault("BTCS_RPC_URL","http://127.0.0.1:18443")
os.environ.setdefault("BTCS_RPC_USER","test")
os.environ.setdefault("BTCS_RPC_PASSWORD","test")
from app import adapters as A

def test_networks():
    assert len(A.NETWORKS) >= 2
    ids = [n.id for n in A.NETWORKS]
    assert "btcs-regtest" in ids
    assert "evm-demo" in ids

def test_btcs_health():
    h = A.btcs_health()
    assert h["chain"] == "regtest"
    assert h["blocks"] >= 0

def test_btcs_recent_blocks():
    bs = A.btcs_recent_blocks(3)
    assert len(bs) == 3
    assert bs[0]["height"] >= bs[1]["height"]

def test_btcs_block_by_height():
    b = A.btcs_block("0")
    assert b["height"] == 0
    assert "hash" in b

def test_evm_adapter():
    b = A.evm_block(1)
    assert b["txCount"] == 2
    try:
        A.evm_block(99)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")

def test_btcs_tx_lookup():
    txid = "e8a1ce419233046dafe149ababdf81cccc6468d0ac64fb9a87cf3c86dc859f47"
    t = __import__("app.adapters", fromlist=["adapters"]).btcs_tx(txid)
    assert t["txid"] == txid
    assert "vout" in t

def test_btcs_block_by_hash():
    from app import adapters as A
    from app import rpc
    bh = rpc.call("http://127.0.0.1:18443","test","test","getbestblockhash",[])
    b = A.btcs_block(bh)
    assert b["hash"] == bh

def test_btcs_address():
    from app import adapters as A
    addr = "bcrt1qf7qj44jf8vm7s4clwvy4vk6rv5k39qcg4pc3d6"
    a = A.btcs_address(addr)
    assert a["address"] == addr
    assert a["balance"] >= 0
    assert "scannedBlocks" in a

def test_btcs_address_invalid():
    from app import adapters as A
    try:
        A.btcs_address("notanaddress")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
