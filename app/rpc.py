import json, urllib.request, base64

class RpcError(Exception):
    pass

def call(url, user, password, method, params=None):
    payload = {"jsonrpc": "1.0", "id": "silverscan", "method": method, "params": params or []}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    if user is not None:
        creds = base64.b64encode(f"{user}:{password}".encode()).decode()
        req.add_header("Authorization", "Basic " + creds)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
    except Exception as e:
        raise RpcError(str(e))
    if body.get("error"):
        raise RpcError(str(body["error"]))
    return body.get("result")
