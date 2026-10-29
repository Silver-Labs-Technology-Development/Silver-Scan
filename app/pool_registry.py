"""Read-only Silver Pool staged-coin registry snapshot.

This is a deliberately conservative copy of public non-secret fields from
Silver-Pool/config/coins.example.json on 2026-10-29.  It is NOT a live pool API
and NEVER implies these coins can be mined here or paid out.
"""
COINS = (
    ("btcs", "Bitcoin Silver", "SHA-256d", "BTCS backend locally tested",
     "https://miningpoolstats.stream/bitcoinsilver"),
    ("btc", "Bitcoin", "SHA-256d", "Disabled staging profile", None),
    ("bch", "Bitcoin Cash", "SHA-256d", "Disabled staging profile", None),
    ("ltc", "Litecoin", "Scrypt", "Disabled staging profile", None),
    ("doge", "Dogecoin", "Scrypt / AuxPoW", "Disabled staging profile", None),
)


def public_coins():
    return {
        "source": "Silver Pool public config/coins.example.json snapshot (2026-10-29)",
        "active_public_pool_coins": 0,
        "ready_for_real_payouts": False,
        "coins": [{
            "id": coin_id, "name": name, "algorithm": algorithm,
            "status": status, "public_mining_enabled": False,
            "payouts_enabled": False,
            "network_hashrate_hps": None,
            "pool_hashrate_hps": None,
            "network_difficulty": None,
            "block_reward": None,
            "block_time_seconds": None,
            "pool_fee_percent": None,
            "miningpoolstats_url": mps,
        } for coin_id, name, algorithm, status, mps in COINS],
        "note": (
            "Offline repository status snapshot, NOT a live coin list or "
            "measured pool stats. Only BTCS has a locally tested mining backend. "
            "BTC/BCH/LTC/DOGE are disabled candidate profiles, not supported "
            "mining endpoints. Actual node metrics must come from connected RPC."
        ),
    }
