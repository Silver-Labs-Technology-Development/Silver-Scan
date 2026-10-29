"""Silver Scan local read-only HTTP server.

The server is intentionally loopback-only by default and must NOT be exposed
directly as a production API. Put a reviewed authenticated/rate-limited proxy
in front before considering any public deployment.
"""
from __future__ import annotations

import json
import re
import ipaddress
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from app import adapters as A
from app import config
from app import indexer as I
from app import market_data as M
from app import coverage as C
from app import pool_registry as P
from app import accounts as U
from app import pool_market as PM
from app import livecoinwatch as LCW
from app import source_status as SS
from app import universal_explorer as UE

STATIC = Path(__file__).resolve().parent / "static"
HEX_HASH = re.compile(r"^[0-9a-fA-F]{64}$")
ADDRESS = re.compile(r"^[A-Za-z0-9]{20,128}$")


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json; charset=utf-8", cookie=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, allow_nan=False)
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        if content_type.startswith("text/html"):
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; img-src 'self' data: https://coin-images.coingecko.com https://assets.coingecko.com https://www.coindesk.com https://www.coindeskcdn.com https://cdn.sanity.io https://cointelegraph.com https://decrypt.co https://www.theblock.co https://bitcoinmagazine.com https://www.bitcoinmagazine.com https://*.btcinc.com; base-uri 'none'; "
                "form-action 'self'; frame-ancestors 'none'",
            )
        self.end_headers()
        self.wfile.write(raw)

    def _error(self, status, message):
        self._send(status, {"error": message})

    # All account APIs are intentionally loopback-only. Do not remove this
    # safeguard to run behind a public reverse proxy without a security audit.
    def _local_account_only(self):
        try:
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                raise PermissionError("Account preview is local-only")
        except ValueError as exc:
            raise PermissionError("Account preview is local-only") from exc

    def _auth_token(self):
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", "")[:4096])
            morsel = jar.get("ss_session")
            return morsel.value if morsel else None
        except Exception:
            return None

    def _current_user(self):
        self._local_account_only()
        return U.session(self._auth_token())

    def _same_origin(self):
        # Require same-origin JSON requests even for registration and login.
        origin = self.headers.get("Origin", "")
        host = self.headers.get("Host", "")
        expected = "http://" + host
        return origin == expected and host.split(":")[0] in ("127.0.0.1", "localhost", "[::1]")

    def _json_body(self):
        if not self._same_origin():
            raise PermissionError("Same-origin account request required")
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            raise ValueError("Account requests require application/json")
        raw_length = self.headers.get("Content-Length", "")
        if not raw_length.isdecimal() or not 1 <= int(raw_length) <= 8192:
            raise ValueError("Invalid account request size")
        try:
            value = json.loads(self.rfile.read(int(raw_length)))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON request") from exc
        if not isinstance(value, dict) or len(value) > 8:
            raise ValueError("Invalid account payload")
        return value

    def _session_cookie(self, token, expires=604800):
        # This is HTTP on a developer loopback server, never public hosting.
        return "ss_session=" + token + "; Path=/; Max-Age=" + str(expires) + "; HttpOnly; SameSite=Strict"

    def _query_int(self, values, key, default, low, high):
        raw = (values.get(key) or [str(default)])[0]
        if not raw.isascii() or not raw.isdecimal():
            raise ValueError(f"{key} must be an integer")
        value = int(raw)
        if not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
        return value

    def _network(self, query):
        selected = (query.get("network") or [A.NETWORKS[0].id])[0]
        network = A.get_network(selected)
        if network is None:
            raise ValueError("Unknown network")
        return network

    def _btcs(self, query):
        network = self._network(query)
        if network.family != "utxo":
            raise ValueError("This endpoint currently supports BTCS L1 only")
        return network

    def _static(self, filename, media_type):
        self._send(200, (STATIC / filename).read_bytes(), media_type)

    def _route(self, path, query):
        if path in ("/", "/index.html"):
            self._static("index.html", "text/html; charset=utf-8")
            return
        if path == "/exchanges.html":
            self._static("exchanges.html", "text/html; charset=utf-8")
            return
        if path == "/exchanges.js":
            self._static("exchanges.js", "application/javascript; charset=utf-8")
            return
        if path == "/universal-explorer.html":
            self._static("universal-explorer.html", "text/html; charset=utf-8")
            return
        if path == "/universal-explorer.js":
            self._static("universal-explorer.js", "application/javascript; charset=utf-8")
            return
        if path == "/feature-detail.html":
            self._static("feature-detail.html", "text/html; charset=utf-8")
            return
        if path in ("/insights.html", "/compare.html"):
            self._static(path.lstrip("/"), "text/html; charset=utf-8")
            return
        if path == "/feature-detail.js":
            self._static("feature-detail.js", "application/javascript; charset=utf-8")
            return
        if path in ("/insights.js", "/compare.js"):
            self._static(path.lstrip("/"), "application/javascript; charset=utf-8")
            return
        if path in ("/coin-watch.html", "/news.html", "/mining.html"):
            self._static(path.lstrip("/"), "text/html; charset=utf-8")
            return
        if path == "/site-shell.js":
            self._static("site-shell.js", "application/javascript; charset=utf-8")
            return
        if path == "/site-shell.css":
            self._static("site-shell.css", "text/css; charset=utf-8")
            return
        if path == "/theme.css":
            self._static("theme.css", "text/css; charset=utf-8")
            return
        if path == "/legacy-hub.js":
            self._static("legacy-hub.js", "application/javascript; charset=utf-8")
            return
        if path == "/portfolio.js":
            self._static("portfolio.js", "application/javascript; charset=utf-8")
            return
        if path == "/theme.js":
            self._static("theme.js", "application/javascript; charset=utf-8")
            return
        if path == "/data-hub.html":
            self._static("data-hub.html", "text/html; charset=utf-8")
            return
        if path == "/data-hub.css":
            self._static("data-hub.css", "text/css; charset=utf-8")
            return
        if path == "/data-hub.js":
            self._static("data-hub.js", "application/javascript; charset=utf-8")
            return
        if path == "/features.html":
            self._static("features.html", "text/html; charset=utf-8")
            return
        if path == "/features.css":
            self._static("features.css", "text/css; charset=utf-8")
            return
        if path == "/features.js":
            self._static("features.js", "application/javascript; charset=utf-8")
            return
        if path == "/styles.css":
            self._static("styles.css", "text/css; charset=utf-8")
            return
        if path == "/charts.js":
            self._static("charts.js", "application/javascript; charset=utf-8")
            return
        if path == "/research.js":
            self._static("research.js", "application/javascript; charset=utf-8")
            return
        if path == "/explorer.js":
            self._static("explorer.js", "application/javascript; charset=utf-8")
            return

        if path == "/api/account/session":
            token = self._auth_token()
            user = self._current_user()
            if not user:
                self._send(200, {"authenticated": False, "local_preview_only": True})
            else:
                csrf = U.rotate_csrf(token, user)
                self._send(200, {"authenticated": True, "email": user["email"],
                                 "csrf": csrf, "local_preview_only": True})
            return
        if path == "/api/account/portfolio":
            self._send(200, U.list_holdings(self._current_user()))
            return
        if path == "/api/networks":
            self._send(200, [n.to_dict() for n in A.NETWORKS])
            return
        if path == "/api/markets":
            self._send(200, M.markets(self._query_int(query, "limit", 50, 1, 100)))
            return
        if path == "/api/catalog/search":
            self._send(200, C.cg_catalog_search((query.get("q") or [""])[0],
                self._query_int(query, "limit", 20, 1, 40)))
            return
        if path == "/api/universal/networks":
            self._send(200, UE.networks())
            return
        if path == "/api/universal/search":
            network=(query.get("network") or [""])[0]
            value=(query.get("q") or [""])[0]
            kind=(query.get("kind") or ["auto"])[0]
            self._send(200, UE.lookup(network,value,kind))
            return
        if path == "/api/sources/status":
            self._send(200, SS.providers())
            return
        if path == "/api/livecoinwatch/markets":
            self._send(200, LCW.market_page(
                self._query_int(query, "page", 1, 1, 500),
                self._query_int(query, "limit", 50, 25, 200)))
            return
        if path == "/api/catalog/page":
            self._send(200, C.cg_market_page(
                self._query_int(query, "page", 1, 1, 500),
                self._query_int(query, "limit", 100, 1, 250)))
            return
        if path == "/api/asset/quote":
            self._send(200, C.cg_quote((query.get("id") or [""])[0]))
            return
        if path == "/api/coinmarketcap/active":
            self._send(200, C.cmc_active(
                self._query_int(query, "page", 1, 1, 200),
                self._query_int(query, "limit", 100, 1, 250)))
            return
        if path == "/api/coinbase/pairs":
            self._send(200, C.coinbase_pairs(
                self._query_int(query, "offset", 0, 0, 10000),
                self._query_int(query, "limit", 100, 1, 100)))
            return
        if path == "/api/news":
            self._send(200, C.news(self._query_int(query, "limit", 20, 1, 40)))
            return
        if path == "/api/insights/trending":
            self._send(200, C.cg_trending())
            return
        if path == "/api/insights/categories":
            self._send(200, C.cg_categories(self._query_int(query, "limit", 30, 1, 50)))
            return
        if path == "/api/insights/exchanges":
            page = self._query_int(query, "page", 1, 1, 20)
            limit = self._query_int(query, "limit", 30, 1, 50)
            self._send(200, C.cg_exchanges(page, limit))
            return
        if path == "/api/insights/defi":
            self._send(200, C.cg_defi())
            return
        if path == "/api/pools/market":
            self._send(200, PM.directory(
                (query.get("coin") or ["all"])[0],
                (query.get("sort") or ["score"])[0],
                self._query_int(query, "limit", 100, 1, 200),
                self._query_int(query, "offset", 0, 0, 2000)))
            return
        if path == "/api/exchanges/cmc":
            self._send(200, C.cmc_exchange_map(
                self._query_int(query, "page", 1, 1, 100),
                self._query_int(query, "limit", 50, 1, 100)))
            return
        if path == "/api/mining/coins":
            self._send(200, P.public_coins())
            return
        if path == "/api/coin-watch/quotes":
            ids = (query.get("ids") or [""])[0].split(",")
            self._send(200, C.cg_market_by_ids(ids))
            return
        if path == "/api/mining/estimate":
            names = ("miner_hashrate_hps","network_hashrate_hps","block_reward",
                     "blocks_per_day","price_usd","fee_percent",
                     "power_watts","electricity_usd_per_kwh")
            self._send(200, C.mining_estimate({n:(query.get(n) or [None])[0] for n in names}))
            return
        if path == "/api/market/global":
            self._send(200, M.global_market())
            return
        if path == "/api/market/sentiment":
            days = self._query_int(query, "days", 30, 7, 90)
            self._send(200, M.market_sentiment(days))
            return
        if path == "/api/assets/profile":
            self._send(200, M.asset_profile((query.get("id") or [""])[0]))
            return
        if path == "/api/assets/chart":
            days = self._query_int(query, "days", 7, 1, 365)
            self._send(200, M.asset_chart((query.get("id") or [""])[0], days))
            return
        if path == "/api/mining/overview":
            self._btcs(query)
            chain = A.btcs_health()
            mining = A.rpc.call(
                config.BTCS_RPC_URL, config.BTCS_RPC_USER, config.BTCS_RPC_PASSWORD,
                "getmininginfo", [],
            )
            if not isinstance(mining, dict):
                raise ValueError("BTCS Core returned invalid mining information")
            self._send(200, {
                "source": "BTCS Core node RPC",
                "network": chain.get("chain"),
                "height": chain.get("blocks"),
                "difficulty": mining.get("difficulty"),
                "network_hashrate_hps": mining.get("networkhashps"),
                "pooled_transactions": mining.get("pooledtx"),
                "chain_synced_progress": chain.get("verificationProgress"),
                "note": "Network-level node information. Not a live pool directory or Silver Pool hashrate.",
                "pool_directory_url": "https://miningpoolstats.stream/bitcoinsilver",
            })
            return
        if path == "/api/dex/search":
            self._send(200, M.dex_search((query.get("q") or [""])[0]))
            return
        if path == "/api/health":
            network = self._network(query)
            if network.family == "utxo":
                self._send(200, A.btcs_health())
            else:
                self._send(200, A.evm_health())  # explicitly fixture-backed demo
            return
        if path == "/api/blocks/recent":
            self._btcs(query)
            limit = self._query_int(query, "limit", 10, 1, 50)
            self._send(200, A.btcs_recent_blocks(limit))
            return
        if path.startswith("/api/block/"):
            network = self._network(query)
            ident = unquote(path[len("/api/block/"):])
            if not (ident.isascii() and ident.isdecimal() and len(ident) <= 10) and not HEX_HASH.fullmatch(ident):
                raise ValueError("Block must be a height or 64-character hash")
            if network.family == "utxo":
                self._send(200, A.btcs_block(ident))
            else:
                self._send(200, A.evm_block(ident))
            return
        if path.startswith("/api/tx/"):
            self._btcs(query)
            txid = unquote(path[len("/api/tx/"):])
            if not HEX_HASH.fullmatch(txid):
                raise ValueError("Invalid transaction ID")
            self._send(200, A.btcs_tx(txid))
            return
        if path == "/api/search":
            self._btcs(query)
            term = (query.get("q") or [""])[0].strip()
            if term.isascii() and term.isdecimal() and len(term) <= 10:
                self._send(200, {"type": "block", "result": A.btcs_block(term)})
            elif HEX_HASH.fullmatch(term):
                try:
                    result = A.btcs_tx(term)
                    self._send(200, {"type": "tx", "result": result})
                except (ValueError, A.rpc.RpcError):
                    self._send(200, {"type": "block", "result": A.btcs_block(term)})
            elif ADDRESS.fullmatch(term):
                self._send(200, {"type": "address", "result": self._address(term, 50, 0)})
            else:
                raise ValueError("Search accepts block height, hash, transaction ID or address")
            return
        if path == "/api/index/status":
            self._btcs(query)
            tip = I.get_tip_info()
            node = A.btcs_health()
            chain_tip = node.get("blocks")
            index_height = tip["height"] if tip is not None else -1
            self._send(200, {
                "tip": index_height,
                "hash": tip["hash"] if tip else None,
                "chain_tip": chain_tip,
                "behind_blocks": max(chain_tip - index_height, 0) if isinstance(chain_tip, int) else None,
                "caught_up": index_height == chain_tip,
                "source": "BTCS Core RPC + local SQLite index",
                "note": "Not a consensus proof. Chain reorganizations are reconciled by the CLI sync.",
            })
            return
        if path == "/api/index/sync":
            self._error(405, "Index writes are disabled over HTTP; use the local CLI")
            return
        if path.startswith("/api/address/"):
            self._btcs(query)
            address = unquote(path[len("/api/address/"):])
            limit = self._query_int(query, "limit", 50, 1, 100)
            offset = self._query_int(query, "offset", 0, 0, 100000)
            self._send(200, self._address(address, limit, offset))
            return
        self._error(404, "Not found")

    def _address(self, address, limit, offset):
        if not ADDRESS.fullmatch(address):
            raise ValueError("Invalid address format")
        validity = A.rpc.call(
            config.BTCS_RPC_URL, config.BTCS_RPC_USER, config.BTCS_RPC_PASSWORD,
            "validateaddress", [address],
        )
        if not isinstance(validity, dict) or not validity.get("isvalid"):
            raise ValueError("Invalid BTCS address")
        return I.address_balance(address, limit, offset)

    def do_GET(self):
        url = urlsplit(self.path)
        try:
            self._route(url.path, parse_qs(url.query, max_num_fields=12))
        except PermissionError as exc:
            self._error(401, str(exc))
        except ValueError as exc:
            self._error(400, str(exc))
        except M.ProviderUnavailable:
            self._error(503, "External market data unavailable; try again later")
        except (A.rpc.RpcError, ConnectionError, OSError, TimeoutError):
            self._error(503, "Required node or index service unavailable")
        except Exception:
            # Never send raw RPC exceptions, stack traces or local paths to browsers.
            self._error(500, "Internal Silver Scan error")

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/api/index/sync":
            self._error(405, "Index writes are disabled over HTTP; use the local CLI")
            return
        if path not in ("/api/account/register", "/api/account/login",
                        "/api/account/logout", "/api/account/portfolio"):
            self._error(405, "This operation is not available")
            return
        try:
            self._local_account_only()
            data = self._json_body()
            if path in ("/api/account/register", "/api/account/login"):
                action = U.register if path.endswith("register") else U.login
                info = action(data.get("email"), data.get("password"),
                              self.client_address[0])
                self._send(200 if path.endswith("login") else 201,
                           {"authenticated": True, "email": info["email"],
                            "csrf": info["csrf"], "local_preview_only": True},
                           cookie=self._session_cookie(info["session"]))
                return
            user = self._current_user()
            csrf = self.headers.get("X-CSRF-Token", "")
            if path == "/api/account/logout":
                U.logout(self._auth_token(), user, csrf)
                self._send(200, {"authenticated": False},
                           cookie=self._session_cookie("", 0))
                return
            self._send(200, U.save_holding(user, csrf, data.get("asset_id"),
                                          data.get("quantity")))
        except U.AccountRateLimit as exc:
            self._error(429, str(exc))
        except PermissionError as exc:
            self._error(403 if "CSRF" in str(exc) or "origin" in str(exc).lower()
                        else 401, str(exc))
        except (ValueError, U.AccountError) as exc:
            self._error(400, str(exc))
        except Exception:
            self._error(500, "Account storage unavailable")

    def do_DELETE(self):
        path = urlsplit(self.path).path
        if not path.startswith("/api/account/portfolio/"):
            self._error(405, "This operation is not available")
            return
        try:
            self._local_account_only()
            if not self._same_origin():
                raise PermissionError("Same-origin account request required")
            user = self._current_user()
            asset = unquote(path[len("/api/account/portfolio/"):])
            U.delete_holding(user, self.headers.get("X-CSRF-Token", ""), asset)
            self._send(200, {"deleted": True, "asset_id": asset})
        except PermissionError as exc:
            self._error(403, str(exc))
        except (ValueError, U.AccountError) as exc:
            self._error(400, str(exc))
        except Exception:
            self._error(500, "Account storage unavailable")

    def log_message(self, format, *args):
        pass


def run():
    I.init_db()
    U.init_db()
    httpd = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    print(f"Silver Scan development server running on http://{config.HOST}:{config.PORT}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
