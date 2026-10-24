import json, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from app.config import HOST, PORT
from app import adapters as A
from app import indexer as I
I.init_db()

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path
        qs = parse_qs(p.query)
        try:
            if path == "/":
                with open(os.path.join(os.path.dirname(__file__), "static", "index.html")) as f:
                    self._send(200, f.read(), "text/html"); return
            if path == "/api/networks":
                self._send(200, json.dumps([n.to_dict() for n in A.NETWORKS])); return
            if path == "/api/health":
                net = (qs.get("network") or ["btcs-regtest"])[0]
                if net.startswith("btcs"):
                    self._send(200, json.dumps(A.btcs_health())); return
                self._send(200, json.dumps(A.evm_health())); return
            if path == "/api/blocks/recent":
                self._send(200, json.dumps(A.btcs_recent_blocks(5))); return
            if path.startswith("/api/block/"):
                ident = path.split("/api/block/",1)[1]
                net = (qs.get("network") or ["btcs-regtest"])[0]
                if net.startswith("btcs"):
                    self._send(200, json.dumps(A.btcs_block(ident))); return
                self._send(200, json.dumps(A.evm_block(ident))); return
            if path.startswith("/api/tx/"):
                txid = path.split("/api/tx/",1)[1]
                self._send(200, json.dumps(A.btcs_tx(txid))); return

            if path == "/api/search":
                q = (qs.get("q") or [""])[0].strip()
                net = (qs.get("network") or ["btcs-regtest"])[0]
                if q.isdigit():
                    self._send(200, json.dumps({"type":"block","result":A.btcs_block(q)})); return
                if len(q)==64:
                    try:
                        self._send(200, json.dumps({"type":"tx","result":A.btcs_tx(q)})); return
                    except Exception:
                        try:
                            self._send(200, json.dumps({"type":"block","result":A.btcs_block(q)})); return
                        except Exception as e:
                            self._send(404, json.dumps({"error":str(e)})); return
                self._send(400, json.dumps({"error":"unrecognized identifier"})); return
            if path == "/api/index/status":
                self._send(200, json.dumps({"tip": I.get_tip(), "db": I.DB_PATH})); return
            if path == "/api/index/sync":
                tip = I.sync_to_tip()
                self._send(200, json.dumps({"syncedTip": tip})); return
            if path.startswith("/api/address/"):
                addr = path.split("/api/address/",1)[1]
                # try indexed first
                try:
                    res = I.address_balance(addr)
                    if res["txCount"]>0 or True:
                        self._send(200, json.dumps(res)); return
                except Exception:
                    pass
                try:
                    self._send(200, json.dumps(A.btcs_address(addr))); return
                except Exception as e:
                    self._send(400, json.dumps({"error": str(e)})); return
            self._send(404, json.dumps({"error":"not found"}))
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))

    def log_message(self, *a):
        pass

def run():
    httpd = HTTPServer((HOST, PORT), Handler)
    print(f"Silver Scan running on http://{HOST}:{PORT}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
