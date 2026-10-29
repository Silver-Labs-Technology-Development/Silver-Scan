"""SilverScan mining-pool comparison: permissioned snapshots only.

No scraping of MiningPoolStats web pages or unofficial endpoints. The
operator asserts a separately authorized JSON dataset with SILVERSCAN_POOL_DATA_PATH and an explicit
SILVERSCAN_POOL_DATA_AUTHORIZED=1. Otherwise expose an honest empty directory.
This does not depend on or imply Silver Pool supports listed chains.
"""
from __future__ import annotations
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

_MAX_SIZE=12_000_000
_MAX_POOLS=20000
_MAX_NETWORKS=2500
_MAX_AGE=24*3600*7
_VALID_SCHEMES={"PPLNS","PPS","FPPS","PROP","SOLO","UNKNOWN"}
_DEFAULT_CG_IDS={"btcs":"bitcoin-silver-2","btc":"bitcoin","bch":"bitcoin-cash","ltc":"litecoin","doge":"dogecoin"}
_ID=re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")

def _number(raw, *, low=0, high=1e30):
    try:
        value=float(raw)
    except (ValueError,TypeError,OverflowError):
        return None
    return value if math.isfinite(value) and low<=value<=high else None

def _https(value):
    if not isinstance(value,str) or len(value)>350:return None
    try:
        parsed=urlsplit(value)
        hostname=parsed.hostname
        if parsed.scheme!="https" or not hostname or parsed.username or parsed.password or parsed.port not in (None,443):return None
        if hostname=="localhost" or hostname.endswith(".local") or hostname.endswith(".internal"):return None
        try:
            addr=ipaddress.ip_address(hostname)
            if not addr.is_global:return None
        except ValueError:pass
    except ValueError:return None
    return value

def _slug(raw):
    return raw if isinstance(raw,str) and _ID.fullmatch(raw) else None

def _timestamp(raw):
    return raw if type(raw) is int and 0<raw<4_100_000_000 else None

def _status(raw):
    return raw if raw in ("online","unknown","offline","stale") else "unknown"

def _snapshot():
    if os.environ.get("SILVERSCAN_POOL_DATA_AUTHORIZED")!="1":
        return None,"Provider-approved MiningPoolStats import not configured"
    path=os.environ.get("SILVERSCAN_POOL_DATA_PATH")
    if not path or not os.path.isabs(path):
        return None,"A private absolute path to an approved pool dataset is required"
    file=Path(path)
    try:
        if not file.is_file() or file.stat().st_size>_MAX_SIZE:
            return None,"Approved pool dataset missing or oversized"
        data=json.loads(file.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError):
        return None,"Approved pool dataset could not be read"
    if not isinstance(data,dict) or data.get("schema_version")!=1:
        return None,"Invalid approved pool dataset schema"
    if data.get("provider")!="MiningPoolStats" or not isinstance(data.get("permission_reference"),str) or len(data["permission_reference"].strip())<8:
        return None,"Dataset must declare provider and documented permission reference"
    if not isinstance(data.get("pools"),list) or not isinstance(data.get("networks"),list):
        return None,"Dataset requires networks and pools"
    if len(data["pools"])>_MAX_POOLS or len(data["networks"]) > _MAX_NETWORKS:
        return None,"Dataset exceeds preview resource limits"
    return data,None

def pool_score(pool,network_hash=None,now=None):
    """Illustrative preference score only if all required observations exist.

    Weights: fee 30%, share 30%, freshness 20%, payout transparency 20%.
    Large pools are not necessarily safer; network share is capped at 30%.
    Scores do not evaluate payout reliability, security or profitability.
    """
    now=int(now or datetime.now(timezone.utc).timestamp())
    fee=pool.get("fee_percent")
    ph=pool.get("pool_hashrate_hps")
    age=pool.get("observed_at")
    scheme=pool.get("payout_method")
    if any(v is None for v in (fee,ph,network_hash,age)) or not scheme or scheme=="UNKNOWN":
        return None
    if network_hash<=0 or age > now+300 or age<now-_MAX_AGE:return None
    share=ph/network_hash
    if not math.isfinite(share) or share<0 or share>1.3:return None
    fee_component=max(0,1-min(fee,5)/5)
    share_component=min(share/.30,1)
    freshness_component=max(0,1-(now-age)/_MAX_AGE)
    return round(100*(.30*fee_component+.30*share_component+
                      .20*freshness_component+.20),1)

def directory(coin="all",sort="score",limit=100,offset=0):
    if coin!="all" and not _slug(coin):raise ValueError("Unknown coin")
    if sort not in ("score","fee","hashrate","name"):raise ValueError("Unknown ranking factor")
    if type(limit) is not int or not 1<=limit<=200:raise ValueError("limit must be 1–200")
    if type(offset) is not int or not 0<=offset<=20000:raise ValueError("offset must be 0–20000")
    dataset,warning=_snapshot()
    now=int(datetime.now(timezone.utc).timestamp())
    result={"source":"Operator-supplied MiningPoolStats-labeled data (permission not independently verified)",
            "provider_data_loaded":bool(dataset),
            "provider_permission_asserted":bool(dataset),
            "networks":[],"pools":[],"total_matching":0,
            "offset":offset,"limit":limit,"sort":sort,"coin":coin,
            "fetched_at":None,"warning":warning,
            "note":"Comparison preference score uses fee (30%), observed network share (30%), freshness (20%) and disclosed payout method (20%). Not a pool safety/reliability certification. Historical or outdated stats must not imply pool activity."}
    if not dataset:return result
    asof=_timestamp(dataset.get("fetched_at"))
    if not asof:return {**result,"warning":"Dataset missing timestamp"}
    age=now-asof
    if age< -300 or age>_MAX_AGE:
        return {**result,"warning":"Data snapshot too old or future-dated; no pool ranking shown"}
    network_map={}
    for item in dataset["networks"]:
        if not isinstance(item,dict):continue
        slug=_slug(item.get("coin"))
        if slug is None or slug in network_map:continue
        row={
            "coin":slug,"coingecko_id":(_slug(item.get("coingecko_id")) or _DEFAULT_CG_IDS.get(slug)),
            "algorithm":str(item.get("algorithm") or "")[:65],
            "network_hashrate_hps":_number(item.get("network_hashrate_hps")),
            "difficulty":_number(item.get("difficulty")),
            "block_reward":_number(item.get("block_reward")),
            "blocks_per_day":_number(item.get("blocks_per_day")),
            "observed_at":_timestamp(item.get("observed_at")),
            "source_url":_https(item.get("source_url")),
        }
        network_map[slug]=row
    result["networks"]=list(network_map.values()) if coin=="all" else list(filter(lambda n:n["coin"]==coin,network_map.values()))
    pool_rows=[]
    for item in dataset["pools"]:
        if not isinstance(item,dict):continue
        slug=_slug(item.get("coin"))
        if slug is None or (coin!="all" and slug!=coin):continue
        name=item.get("name")
        if not isinstance(name,str) or not 1<=len(name.strip())<=120:continue
        net=network_map.get(slug)
        row={
            "coin":slug,"name":name.strip(),
            "pool_id":str(item.get("pool_id") or "")[:100],
            "url":_https(item.get("url")),
            "source_url":_https(item.get("source_url")),
            "payout_method":item.get("payout_method") if item.get("payout_method") in _VALID_SCHEMES else "UNKNOWN",
            "fee_percent":_number(item.get("fee_percent"),high=100),
            "pool_hashrate_hps":_number(item.get("pool_hashrate_hps")),
            "miners":_number(item.get("miners"),high=1e10),
            "minimum_payout":_number(item.get("minimum_payout")),
            "observed_at":_timestamp(item.get("observed_at")),
            "status":_status(item.get("status")),
            "source":"MiningPoolStats import"
        }
        nh=net["network_hashrate_hps"] if net else None
        row["network_share_pct"]=round(row["pool_hashrate_hps"]/nh*100,2) if nh and row["pool_hashrate_hps"] is not None else None
        row["preference_score"]=pool_score(row,nh,now) if row["status"]=="online" else None
        pool_rows.append(row)
    result["total_matching"]=len(pool_rows)
    if sort=="name":pool_rows.sort(key=lambda r:(r["name"].lower(),r["coin"]))
    elif sort=="fee":pool_rows.sort(key=lambda r:(r["fee_percent"] is None,r["fee_percent"] if r["fee_percent"] is not None else 0,r["name"].lower()))
    elif sort=="hashrate":pool_rows.sort(key=lambda r:(r["pool_hashrate_hps"] is None,-(r["pool_hashrate_hps"] or 0),r["name"].lower()))
    else:pool_rows.sort(key=lambda r:(r["preference_score"] is None,-(r["preference_score"] or 0),r["name"].lower()))
    result["pools"]=pool_rows[offset:offset+limit]
    result["fetched_at"]=asof
    result["warning"]=None if age<3600 else "Dataset older than one hour; compare freshness before relying on statistics"
    return result
