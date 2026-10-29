"""SilverScan's read-only universal blockchain explorer adapter.

Network-specific read-only RPC is intentionally NOT an indexer and does not
claim complete holder rankings, transfers, address histories or NFT catalogs.
Only fixed operator-selected endpoints are used. No arbitrary proxy URLs,
transaction signing, gas spending, or credentials exposed to browsers.
"""
from __future__ import annotations
from decimal import Decimal
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.market_data import ProviderUnavailable

EVM = {
    "ethereum": {"name":"Ethereum","chain_id":1,"symbol":"ETH",
                 "env":"SILVERSCAN_ETHEREUM_RPC","default":"https://ethereum-rpc.publicnode.com"},
    "bsc": {"name":"BNB Smart Chain","chain_id":56,"symbol":"BNB",
            "env":"SILVERSCAN_BSC_RPC","default":"https://bsc-dataseed.bnbchain.org"},
    "base": {"name":"Base","chain_id":8453,"symbol":"ETH",
             "env":"SILVERSCAN_BASE_RPC","default":"https://mainnet.base.org"},
    "polygon": {"name":"Polygon PoS","chain_id":137,"symbol":"POL",
                "env":"SILVERSCAN_POLYGON_RPC","default":None},
    "arbitrum": {"name":"Arbitrum One","chain_id":42161,"symbol":"ETH",
                 "env":"SILVERSCAN_ARBITRUM_RPC","default":"https://arb1.arbitrum.io/rpc"},
    "avalanche": {"name":"Avalanche C-Chain","chain_id":43114,"symbol":"AVAX",
                  "env":"SILVERSCAN_AVALANCHE_RPC","default":None},
}
SOLANA = {"name":"Solana","symbol":"SOL",
          "env":"SILVERSCAN_SOLANA_RPC","default":"https://api.mainnet.solana.com"}
_EVM_ADDR = re.compile(r"^0x[a-fA-F0-9]{40}$")
_EVM_TX = re.compile(r"^0x[a-fA-F0-9]{64}$")
_SOL_ADDR = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_SOL_TX = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{80,90}$")
_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
_TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
_MAX_BODY = 2_000_000

def networks():
    result=[{"id":key,"name":cfg["name"],"family":"EVM",
             "chain_id":cfg["chain_id"],"currency":cfg["symbol"],
             "configured":bool(os.getenv(cfg["env"]) or cfg["default"]),
             "data_level":"read-only RPC; not indexed address history"} for key,cfg in EVM.items()]
    result.append({"id":"solana","name":"Solana","family":"Solana",
                   "chain_id":None,"currency":"SOL",
                   "configured":bool(os.getenv(SOLANA["env"]) or SOLANA["default"]),
                   "data_level":"read-only RPC; short recent-signature history"})
    result.insert(0,{"id":"btcs","name":"Bitcoin Silver L1","family":"Bitcoin-like UTXO",
                     "chain_id":None,"currency":"BTCS","configured":True,
                     "data_level":"existing SilverScan Bitcoin Silver Core/indexer endpoints"})
    return {"networks":result,
            "source":"SilverScan adapter registry",
            "note":"Configured is not an availability check. Live reads may be rate-limited. A market-data coin catalog does not imply explorer integration."}

def _endpoint(cfg):
    endpoint=(os.getenv(cfg["env"]) or cfg["default"] or "").strip()
    if not endpoint:
        raise ProviderUnavailable("This chain needs a configured RPC provider")
    parts=urlsplit(endpoint)
    if (parts.scheme!="https" or not parts.hostname or parts.username or parts.password
            or parts.port not in (None,443) or len(endpoint)>500 or parts.fragment):
        raise ProviderUnavailable("Invalid chain RPC configuration; HTTPS provider required")
    return endpoint

def _rpc(endpoint,method,params):
    if method not in {
        "eth_chainId","eth_getBalance","eth_getCode","eth_getTransactionCount",
        "eth_getTransactionByHash","eth_getTransactionReceipt",
        "eth_getBlockByNumber","eth_call",
        "getAccountInfo","getBalance","getTokenSupply",
        "getSignaturesForAddress","getTransaction","getBlock",
        "getTokenAccountsByOwner"
    }:
        raise ValueError("RPC method not permitted")
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params},
                    separators=(",",":")).encode()
    if len(body)>10000:
        raise ValueError("RPC request too large")
    req=Request(endpoint,data=body,headers={
        "Content-Type":"application/json","Accept":"application/json",
        "User-Agent":"SilverScan-ReadOnly/1.0"
    },method="POST")
    try:
        with urlopen(req,timeout=7) as response:
            original=urlsplit(endpoint)
            redirect=urlsplit(response.geturl())
            if (redirect.scheme!="https" or redirect.hostname!=original.hostname):
                raise ProviderUnavailable("RPC redirect refused")
            raw=response.read(_MAX_BODY+1)
        if len(raw)>_MAX_BODY:
            raise ProviderUnavailable("RPC response exceeded safety limit")
        data=json.loads(raw)
        if not isinstance(data,dict):
            raise ProviderUnavailable("Invalid RPC response")
        if data.get("error"):
            raise ProviderUnavailable("RPC provider reported an unsupported or unavailable query")
        return data.get("result")
    except (HTTPError,URLError,OSError,TimeoutError,ValueError,UnicodeDecodeError) as exc:
        raise ProviderUnavailable("Blockchain RPC unavailable, rate-limited, or returned invalid data") from exc

def _int(value):
    try:
        return int(value,16) if isinstance(value,str) and value.startswith("0x") else None
    except ValueError:
        return None

def _sol_number(value):
    return value if type(value) is int and value>=0 else None

def _hex_decimal(value,decimals=18):
    integer=_int(value)
    if integer is None:return None
    return format(Decimal(integer)/(Decimal(10)**decimals),"f")

def _erc20(endpoint,address):
    selectors={"name":"0x06fdde03","symbol":"0x95d89b41",
               "decimals":"0x313ce567","total_supply":"0x18160ddd"}
    data={}
    for key,selector in selectors.items():
        try:
            value=_rpc(endpoint,"eth_call",[{"to":address,"data":selector},"latest"])
            if not isinstance(value,str) or not value.startswith("0x") or len(value)>512:
                continue
            raw=bytes.fromhex(value[2:])
            if key in ("name","symbol"):
                # ERC-20 strings may return dynamic ABI-encoded strings or bytes32.
                try:
                    if len(raw)>=96 and int.from_bytes(raw[:32],"big")==32:
                        size=int.from_bytes(raw[32:64],"big")
                        result=raw[64:64+min(size,64)].decode("utf-8",errors="replace")
                    else:
                        result=raw[:32].rstrip(b"\x00").decode("utf-8",errors="replace")
                    data[key]=result[:64] if result.isprintable() and result else None
                except (UnicodeDecodeError,ValueError):
                    continue
            else:
                data[key]=int.from_bytes(raw,"big")
        except (ProviderUnavailable,ValueError):
            continue
    if isinstance(data.get("decimals"),int) and 0<=data["decimals"]<=36:
        data["display_total_supply"]=(
            format(Decimal(data["total_supply"])/(Decimal(10)**data["decimals"]),"f")
            if isinstance(data.get("total_supply"),int) else None)
    else:
        data["display_total_supply"]=None
    data.pop("total_supply",None)
    return data

def _evm(chain,query,kind):
    cfg=EVM[chain]
    endpoint=_endpoint(cfg)
    root={"network":chain,"network_name":cfg["name"],"family":"EVM",
          "chain_id":cfg["chain_id"],"currency":cfg["symbol"],
          "source":"Chain-specific Ethereum JSON-RPC","observed_at":int(time.time()),
          "indexed_history":False}
    try:
        actual=_int(_rpc(endpoint,"eth_chainId",[]))
    except ProviderUnavailable:
        raise
    if actual!=cfg["chain_id"]:
        raise ProviderUnavailable("RPC provider returned a different chain ID; results rejected")
    if kind in ("auto","address","token") and _EVM_ADDR.fullmatch(query):
        balance=_rpc(endpoint,"eth_getBalance",[query,"latest"])
        code=_rpc(endpoint,"eth_getCode",[query,"latest"])
        nonce=_rpc(endpoint,"eth_getTransactionCount",[query,"latest"])
        is_contract=isinstance(code,str) and code not in ("0x","0x0","0x00")
        result={**root,"type":"contract" if is_contract else "address",
                "address":query,"native_balance":_hex_decimal(balance),
                "transaction_nonce":_int(nonce),"is_contract":is_contract,
                "message":"Native balance and nonce from RPC. Full token portfolio and historical transfers require an indexed provider."}
        if is_contract:
            result["token_metadata"]=_erc20(endpoint,query)
        return result
    if kind in ("auto","transaction") and _EVM_TX.fullmatch(query):
        tx=_rpc(endpoint,"eth_getTransactionByHash",[query])
        if not isinstance(tx,dict):
            return {**root,"type":"transaction","query":query,"found":False}
        receipt=_rpc(endpoint,"eth_getTransactionReceipt",[query])
        return {**root,"type":"transaction","found":True,"hash":tx.get("hash"),
                "from":tx.get("from"),"to":tx.get("to"),
                "block_number":_int(tx.get("blockNumber")),
                "value_native":_hex_decimal(tx.get("value")),
                "gas_limit":_int(tx.get("gas")),
                "gas_price_wei":_int(tx.get("gasPrice")),
                "status":_int(receipt.get("status")) if isinstance(receipt,dict) else None,
                "gas_used":_int(receipt.get("gasUsed")) if isinstance(receipt,dict) else None,
                "log_count":len(receipt.get("logs") or []) if isinstance(receipt,dict) else None,
                "message":"Raw RPC transaction summary. Token transfers and decoded event labels require a verified indexer."}
    if kind in ("auto","block") and query.isdecimal() and len(query)<18:
        height=int(query)
        if height<0 or height>2**53:
            raise ValueError("Invalid block height")
        block=_rpc(endpoint,"eth_getBlockByNumber",[hex(height),False])
        if not isinstance(block,dict):
            return {**root,"type":"block","height":height,"found":False}
        return {**root,"type":"block","found":True,"height":height,
                "hash":block.get("hash"),"timestamp":_int(block.get("timestamp")),
                "transaction_count":len(block.get("transactions") or []),
                "gas_used":_int(block.get("gasUsed")),
                "gas_limit":_int(block.get("gasLimit")),
                "miner":block.get("miner")}
    raise ValueError("Enter a valid EVM address, transaction hash, or block number")

def _solana(query,kind):
    endpoint=_endpoint(SOLANA)
    root={"network":"solana","network_name":"Solana","family":"Solana",
          "currency":"SOL","source":"Solana JSON-RPC (mainnet)",
          "observed_at":int(time.time()),"indexed_history":False}
    if kind in ("auto","address","token") and _SOL_ADDR.fullmatch(query):
        balance=_rpc(endpoint,"getBalance",[query,{"commitment":"confirmed"}])
        account=_rpc(endpoint,"getAccountInfo",[query,{"encoding":"jsonParsed",
                                                        "commitment":"confirmed"}])
        account_value=account.get("value") if isinstance(account,dict) else None
        lamports=balance.get("value") if isinstance(balance,dict) else None
        info=account_value if isinstance(account_value,dict) else {}
        result={**root,"type":"account","address":query,
                "native_balance":str(Decimal(lamports)/Decimal(1_000_000_000))
                  if type(lamports) is int and lamports>=0 else None,
                "program_owner":info.get("owner"),"executable":info.get("executable"),
                "space":info.get("space"),
                "message":"Confirmed account RPC observations. A Solana account may be a wallet, token account, mint or executable program."}
        parsed=info.get("data") if isinstance(info.get("data"),dict) else {}
        token=parsed.get("parsed") if isinstance(parsed.get("parsed"),dict) else {}
        if token:
            result["parsed_account_type"]=token.get("type")
            token_data=token.get("info") if isinstance(token.get("info"),dict) else {}
            result["token_mint"]=token_data.get("mint")
            result["token_decimals"]=(token_data.get("decimals")
                         if type(token_data.get("decimals")) is int else None)
            result["token_supply_raw"]=token_data.get("supply")
        try:
            sigs=_rpc(endpoint,"getSignaturesForAddress",[query,{"limit":8}])
            if isinstance(sigs,list):
                result["recent_signatures"]=[{"signature":x.get("signature"),
                    "slot":x.get("slot"),"err":x.get("err"),
                    "block_time":x.get("blockTime")} for x in sigs[:8] if isinstance(x,dict)]
        except ProviderUnavailable:
            result["recent_signatures_unavailable"]=True
        if info.get("owner") in (_TOKEN_PROGRAM,_TOKEN_2022):
            try:
                supply=_rpc(endpoint,"getTokenSupply",[query,{"commitment":"confirmed"}])
                amount=supply.get("value") if isinstance(supply,dict) else None
                if isinstance(amount,dict):
                    result["token_supply"]=amount.get("uiAmountString")
                    result["token_supply_decimals"]=amount.get("decimals")
            except ProviderUnavailable:
                pass
        return result
    if kind in ("auto","transaction") and _SOL_TX.fullmatch(query):
        tx=_rpc(endpoint,"getTransaction",[query,{"encoding":"jsonParsed",
                     "commitment":"confirmed","maxSupportedTransactionVersion":0}])
        if not isinstance(tx,dict):
            return {**root,"type":"transaction","found":False,"query":query}
        meta=tx.get("meta") if isinstance(tx.get("meta"),dict) else {}
        transaction=tx.get("transaction") if isinstance(tx.get("transaction"),dict) else {}
        message=transaction.get("message") if isinstance(transaction.get("message"),dict) else {}
        return {**root,"type":"transaction","found":True,"signature":query,
                "slot":tx.get("slot"),"block_time":tx.get("blockTime"),
                "fee_lamports":meta.get("fee"),"error":meta.get("err"),
                "instruction_count":len(message.get("instructions") or []),
                "token_balance_changes":len(meta.get("postTokenBalances") or []),
                "message":"Transaction summary only. Full instruction and token movement decoding requires network-specific parsers."}
    if kind in ("auto","block") and query.isdecimal() and len(query)<18:
        slot=int(query)
        if slot>2**53:raise ValueError("Invalid Solana slot")
        block=_rpc(endpoint,"getBlock",[slot,{"encoding":"json",
                  "transactionDetails":"signatures","rewards":False,
                  "maxSupportedTransactionVersion":0}])
        if not isinstance(block,dict):
            return {**root,"type":"block","found":False,"slot":slot}
        return {**root,"type":"block","found":True,"slot":slot,
                "blockhash":block.get("blockhash"),
                "previous_blockhash":block.get("previousBlockhash"),
                "block_time":block.get("blockTime"),
                "block_height":block.get("blockHeight"),
                "transaction_count":len(block.get("signatures") or []),
                "message":"Solana slots can be skipped; a slot is not always a confirmed block."}
    raise ValueError("Enter a valid Solana base58 account/mint, signature, or numeric slot")

def lookup(network,query,kind="auto"):
    if not isinstance(query,str) or len(query)>110 or query!=query.strip():
        raise ValueError("Enter a valid address, transaction, mint or block")
    if kind not in ("auto","address","transaction","block","token"):
        raise ValueError("Unsupported lookup type")
    if network in EVM:return _evm(network,query,kind)
    if network=="solana":return _solana(query,kind)
    raise ValueError("Unsupported chain. Bitcoin Silver uses its existing BTCS explorer.")
