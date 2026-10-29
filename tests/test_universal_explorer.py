"""Universal Explorer chain adapters: read-only, deterministic offline tests."""
from unittest.mock import patch

import pytest

from app import universal_explorer as U
from app.market_data import ProviderUnavailable


ETH_ADDR = "0x" + "a"*40
TX_HASH = "0x" + "b"*64
SOL_ADDR = "11111111111111111111111111111111"
SOL_TX = "3"*88


def test_registry_includes_bsc_ethereum_solana_and_more():
    rows=U.networks()["networks"]
    chains={r["id"] for r in rows}
    assert {"btcs","ethereum","bsc","solana","base","polygon","arbitrum","avalanche"} <= chains
    assert next(r for r in rows if r["id"]=="bsc")["chain_id"]==56
    assert next(r for r in rows if r["id"]=="solana")["family"]=="Solana"


def test_evm_address_balance_and_noncustodial_contract_discovery():
    def rpc(endpoint,method,params):
        return {
            "eth_chainId":"0x1",
            "eth_getBalance":hex(2*10**18),
            "eth_getCode":"0x608060",
            "eth_getTransactionCount":"0x3",
            "eth_call":"0x",
        }[method]
    with patch.object(U,"_rpc",side_effect=rpc):
        result=U.lookup("ethereum",ETH_ADDR)
    assert result["network"]=="ethereum"
    assert result["native_balance"]=="2"
    assert result["transaction_nonce"]==3
    assert result["type"]=="contract"
    assert result["is_contract"] is True
    assert result["indexed_history"] is False


def test_evm_transaction_status_uses_receipt_and_chain_identity():
    def rpc(endpoint,method,params):
        if method=="eth_chainId":return "0x38"
        if method=="eth_getTransactionByHash":
            return {"hash":TX_HASH,"from":ETH_ADDR,"to":"0x"+"f"*40,
                    "blockNumber":"0xaa","value":hex(10**18),
                    "gas":"0x5208","gasPrice":"0x3b9aca00"}
        if method=="eth_getTransactionReceipt":
            return {"status":"0x1","gasUsed":"0x5208","logs":[{},{}]}
        raise AssertionError(method)
    with patch.object(U,"_rpc",side_effect=rpc):
        result=U.lookup("bsc",TX_HASH,"transaction")
    assert result["chain_id"]==56
    assert result["block_number"]==170
    assert result["gas_used"]==21000
    assert result["log_count"]==2
    assert result["value_native"]=="1"
    assert result["status"]==1


def test_evm_block_and_missing_tx_not_invented():
    with patch.object(U,"_rpc",side_effect=lambda endpoint,method,params: {
        "eth_chainId":"0x1",
        "eth_getBlockByNumber":{"number":"0x8","hash":TX_HASH,
                                "timestamp":"0x7b","transactions":[TX_HASH],"gasUsed":"0x5",
                                "gasLimit":"0x100","miner":ETH_ADDR}
    }[method]):
        result=U.lookup("ethereum","8","block")
    assert result["transaction_count"]==1
    assert result["timestamp"]==123
    with patch.object(U,"_rpc",side_effect=lambda endpoint,method,params:
                      "0x1" if method=="eth_chainId" else None):
        tx=U.lookup("ethereum",TX_HASH)
    assert tx["found"] is False


def test_wrong_network_rpc_rejected_before_showing_false_data():
    with patch.object(U,"_rpc",return_value="0x1"):
        with pytest.raises(ProviderUnavailable,match="different chain ID"):
            U.lookup("bsc",ETH_ADDR,"address")


def test_solana_address_and_token_supply_rpc_schema():
    def rpc(endpoint,method,params):
        if method=="getBalance":return {"value":2_500_000_000}
        if method=="getAccountInfo":
            return {"value":{"owner":U._TOKEN_PROGRAM,"executable":False,
                             "space":82,"data":{"parsed":{"type":"mint",
                             "info":{"decimals":9,"supply":"10000000000"}}}}}
        if method=="getSignaturesForAddress":
            return [{"signature":SOL_TX,"slot":120,"err":None,"blockTime":1780000000}]
        if method=="getTokenSupply":
            return {"value":{"amount":"10000000000","decimals":9,"uiAmountString":"10"}}
        raise AssertionError(method)
    with patch.object(U,"_rpc",side_effect=rpc):
        result=U.lookup("solana",SOL_ADDR,"token")
    assert result["native_balance"]=="2.5"
    assert result["token_supply"]=="10"
    assert result["recent_signatures"][0]["signature"]==SOL_TX
    assert result["source"].startswith("Solana JSON-RPC")


def test_solana_transaction_and_skipped_slot():
    with patch.object(U,"_rpc",return_value={
        "slot":125,"blockTime":1780000000,
        "meta":{"fee":5000,"err":None,"postTokenBalances":[{}]},
        "transaction":{"message":{"instructions":[{},{}]}}
    }):
        result=U.lookup("solana",SOL_TX,"transaction")
    assert result["slot"]==125
    assert result["fee_lamports"]==5000
    assert result["token_balance_changes"]==1
    with patch.object(U,"_rpc",return_value=None):
        result=U.lookup("solana","123","block")
    assert result["found"] is False


@pytest.mark.parametrize("network,query",[
    ("bsc","javascript:alert(1)"),
    ("ethereum","0x123"),
    ("solana","../etc/passwd"),
    ("polygon",TX_HASH+"notvalid"),
    ("arbitrum","not-an-address"),
    ("avalanche","5"*112),
    ("unknown",ETH_ADDR)
])
def test_invalid_chain_or_search_rejected(network,query):
    with pytest.raises((ValueError,ProviderUnavailable)):
        U.lookup(network,query)


def test_rpc_methods_are_allowlisted():
    with pytest.raises(ValueError,match="not permitted"):
        U._rpc("https://example.com","eth_sendTransaction",[])
    with pytest.raises(ValueError,match="not permitted"):
        U._rpc("https://example.com","sendTransaction",[])


def test_unconfigured_endpoint_fails_without_probing_unknown_hosts(monkeypatch):
    monkeypatch.delenv("SILVERSCAN_POLYGON_RPC",raising=False)
    with pytest.raises(ProviderUnavailable,match="configured RPC"):
        U.lookup("polygon",ETH_ADDR)
