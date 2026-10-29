"""Offline tests for local-only SilverScan account/portfolio storage and HTTP guards."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from app import accounts as U
from app import main


@pytest.fixture(autouse=True)
def isolated_accounts(tmp_path,monkeypatch):
    monkeypatch.setenv("SILVERSCAN_ACCOUNT_DB",str(tmp_path/"accounts.sqlite3"))
    U._ATTEMPTS.clear()
    U.init_db()


def test_account_password_hashing_isolation_and_session_revocation():
    a=U.register("a@example.org","a-long-password-example")
    b=U.register("b@example.org","another-long-password")
    assert a["email"]=="a@example.org"
    assert a["session"] != b["session"]
    ua=U.session(a["session"]);ub=U.session(b["session"])
    assert ua is not None and ub is not None and ua["id"]!=ub["id"]
    data=U.save_holding(ua,a["csrf"],"coingecko:bitcoin-silver-2","1234.567")
    assert data["quantity"]=="1234.567"
    assert U.list_holdings(ua)["holdings"][0]["asset_id"]=="coingecko:bitcoin-silver-2"
    assert U.list_holdings(ub)["holdings"]==[]
    with pytest.raises(PermissionError):
        U.save_holding(ub,a["csrf"],"coingecko:bitcoin-silver-2","111")
    assert U.list_holdings(ub)["holdings"]==[]
    U.save_holding(ub,b["csrf"],"coingecko:bitcoin-silver-2","21.000")
    assert U.list_holdings(ub)["holdings"][0]["quantity"]=="21"
    U.delete_holding(ua,a["csrf"],"coingecko:bitcoin-silver-2")
    assert U.list_holdings(ua)["holdings"]==[]
    assert len(U.list_holdings(ub)["holdings"])==1
    U.logout(a["session"],ua,a["csrf"])
    assert U.session(a["session"]) is None
    with pytest.raises(PermissionError):
        U.list_holdings(None)
    assert U.login("B@example.org","another-long-password")["email"]=="b@example.org"


def test_amounts_coin_identity_and_passwords_are_validated():
    with pytest.raises(U.AccountError):
        U.register("n@example.org","short")
    a=U.register("user@example.org","long-enough-password")
    with pytest.raises(U.AccountError):
        U.login("user@example.org","wrong-password")
    user=U.session(a["session"])
    for qty in ["-1","1e10","Infinity","1,000"," 50 ","0.0000000000000000001"]:
        with pytest.raises(U.AccountError):
            U.save_holding(user,a["csrf"],"coingecko:bitcoin",qty)
    for coin in ["BTC","coinmarketcap:1","coingecko:BTC","coingecko:..","coingecko:"]:
        with pytest.raises(U.AccountError):
            U.save_holding(user,a["csrf"],coin,"10")
    assert U._db_path().stat().st_mode & 0o777 == 0o600


@pytest.fixture
def api():
    server=ThreadingHTTPServer(("127.0.0.1",0),main.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:"+str(server.server_port)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


def request(base,path,method="GET",payload=None,cookie=None,csrf=None,origin=True):
    data=json.dumps(payload).encode() if payload is not None else None
    headers={}
    if data is not None:headers["Content-Type"]="application/json"
    if origin:headers["Origin"]=base
    if cookie:headers["Cookie"]=cookie
    if csrf:headers["X-CSRF-Token"]=csrf
    req=Request(base+path,data=data,headers=headers,method=method)
    try:
        with urlopen(req,timeout=3) as r:return r.status,dict(r.headers),json.loads(r.read())
    except HTTPError as exc:return exc.code,dict(exc.headers),json.loads(exc.read())


def test_real_http_register_add_holdings_logout_and_csrf(api):
    status,headers,data=request(api,"/api/account/register",method="POST",
                                payload={"email":"http@example.org","password":"long-password-for-testing"})
    assert status==201 and data["authenticated"] is True
    assert "HttpOnly" in headers["Set-Cookie"] and "SameSite=Strict" in headers["Set-Cookie"]
    cookie=headers["Set-Cookie"].split(";",1)[0]
    csrf=data["csrf"]
    status,_,session=request(api,"/api/account/session",cookie=cookie)
    assert status==200 and session["authenticated"]
    csrf=session["csrf"]  # Rotated after reload: old CSRF must now fail.
    status,_,bad=request(api,"/api/account/portfolio",method="POST",cookie=cookie,
                          payload={"asset_id":"coingecko:bitcoin","quantity":"2"},
                          csrf="bad")
    assert status==403 and "error" in bad
    status,_,result=request(api,"/api/account/portfolio",method="POST",cookie=cookie,
                             csrf=csrf,payload={"asset_id":"coingecko:bitcoin-silver-2","quantity":"3.5"})
    assert status==200 and result["quantity"]=="3.5"
    status,_,portfolio=request(api,"/api/account/portfolio",cookie=cookie)
    assert status==200 and portfolio["verified"] is False
    assert portfolio["holdings"][0]["quantity"]=="3.5"
    status,_,unauthorized=request(api,"/api/account/portfolio")
    assert status==401 and "error" in unauthorized
    status,_,forbidden=request(api,"/api/account/portfolio",method="POST",cookie=cookie,
                               csrf=csrf,payload={"asset_id":"coingecko:bitcoin","quantity":"2"},
                               origin=False)
    assert status in (401,403)
    status,_,deleted=request(api,"/api/account/portfolio/coingecko%3Abitcoin-silver-2",
                              method="DELETE",cookie=cookie,csrf=csrf)
    assert status==200 and deleted["deleted"]
    status,_,done=request(api,"/api/account/logout",method="POST",cookie=cookie,csrf=csrf,payload={})
    assert status==200 and not done["authenticated"]
    status,_,after=request(api,"/api/account/session",cookie=cookie)
    assert status==200 and after["authenticated"] is False


def test_database_persists_saved_holdings_across_connections():
    a=U.register("persistent@example.org","this-is-long-password")
    user=U.session(a["session"])
    U.save_holding(user,a["csrf"],"coingecko:bitcoin-silver-2","5000")
    for _ in range(3):
        holdings=U.list_holdings(U.session(a["session"]))["holdings"]
        assert holdings[0]["quantity"]=="5000"
