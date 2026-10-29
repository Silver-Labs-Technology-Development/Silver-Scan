import os

def env(key, default=None):
    return os.environ.get(key, default)

BTCS_RPC_URL = env("BTCS_RPC_URL", "http://127.0.0.1:18443")
BTCS_RPC_USER = env("BTCS_RPC_USER", "test")
BTCS_RPC_PASSWORD = env("BTCS_RPC_PASSWORD", "test")
BTCS_NETWORK = env("BTCS_NETWORK", "regtest")
HOST = env("HOST", "127.0.0.1")
PORT = int(env("PORT", "8000"))
