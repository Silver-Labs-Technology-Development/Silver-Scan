"""Local-only SilverScan manual portfolio accounts.

This is a development feature, not a public account service. No wallet keys,
deposits or proof of ownership are collected. Never expose the stdlib HTTP
server directly to the Internet. Production needs independent auth/security
review, TLS, durable storage, backup/recovery and abuse prevention.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time

_DB_ENV = "SILVERSCAN_ACCOUNT_DB"
_ACCOUNT_LOCK = threading.RLock()
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,30}$")
_COIN = re.compile(r"^coingecko:[a-z0-9][a-z0-9-]{0,99}$")
_PASSWORD_MIN = 12
_MAX_POSITIONS = 100
_DURATION = 7 * 24 * 3600
_COST = 2**14
_ATTEMPTS: dict[str, list[float]] = {}
_DUMMY_SALT = b"SilverScanNoAccountSalt00000000"


class AccountError(ValueError):
    """Validated user input or account-session failure."""


class AccountRateLimit(AccountError):
    """Too many login attempts from a client."""


def _db_path() -> Path:
    return Path(os.environ.get(_DB_ENV) or
                (Path.home() / ".local" / "share" / "silverscan" / "accounts.sqlite3"))


def _db():
    path = _db_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.exists():
        fd = os.open(str(path), os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with _ACCOUNT_LOCK, _db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            salt BLOB NOT NULL, password_hash BLOB NOT NULL,
            created_at INTEGER NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS sessions(
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            csrf_hash TEXT NOT NULL, expires_at INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS holdings(
            user_id INTEGER NOT NULL, asset_id TEXT NOT NULL,
            quantity TEXT NOT NULL, updated_at INTEGER NOT NULL,
            PRIMARY KEY(user_id,asset_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at)")


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt,
                         n=_COST, r=8, p=1, dklen=32)


def _email(raw):
    if not isinstance(raw, str):
        raise AccountError("Enter an email address")
    value = raw.strip().lower()
    if len(value) > 254 or not _EMAIL.fullmatch(value):
        raise AccountError("Enter a valid email address")
    return value


def _password(raw, registering=False):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 256:
        raise AccountError("Invalid password")
    if registering and len(raw) < _PASSWORD_MIN:
        raise AccountError("Password must contain at least 12 characters")
    if not raw:
        raise AccountError("Invalid password")
    return raw


def _rate_limit(remote: str):
    # Backend binds loopback by default; do not trust forwarded-for strings.
    now = time.monotonic()
    with _ACCOUNT_LOCK:
        entries = [t for t in _ATTEMPTS.get(remote, []) if now-t < 600]
        if len(entries) >= 12:
            raise AccountRateLimit("Too many attempts. Try later.")
        entries.append(now)
        _ATTEMPTS[remote] = entries
        if len(_ATTEMPTS) > 1000:
            _ATTEMPTS.clear()


def _issue(conn, user_id: int):
    token = secrets.token_urlsafe(36)
    csrf = secrets.token_urlsafe(32)
    now = int(time.time())
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    conn.execute(
        "INSERT INTO sessions(token_hash,user_id,csrf_hash,expires_at) VALUES(?,?,?,?)",
        (_digest(token), user_id, _digest(csrf), now + _DURATION),
    )
    return {"session": token, "csrf": csrf, "expires_at": now + _DURATION}


def register(email, password, remote="local"):
    _rate_limit(remote)
    email = _email(email)
    password = _password(password, registering=True)
    salt = secrets.token_bytes(32)
    computed = _password_hash(password, salt)
    with _ACCOUNT_LOCK, _db() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users(email,salt,password_hash,created_at) VALUES(?,?,?,?)",
                (email, salt, computed, int(time.time())),
            )
        except sqlite3.IntegrityError as exc:
            raise AccountError("Account already exists. Sign in instead.") from exc
        result = _issue(conn, cursor.lastrowid)
    return {"email": email, **result}


def login(email, password, remote="local"):
    _rate_limit(remote)
    email = _email(email)
    password = _password(password)
    with _ACCOUNT_LOCK, _db() as conn:
        row = conn.execute("SELECT id,email,salt,password_hash FROM users WHERE email=?",
                           (email,)).fetchone()
        salt = row["salt"] if row else _DUMMY_SALT
        candidate = _password_hash(password, salt)
        if row is None or not hmac.compare_digest(candidate, row["password_hash"]):
            raise AccountError("Invalid email or password")
        result = _issue(conn, row["id"])
        return {"email": row["email"], **result}


def session(token: str | None):
    if not isinstance(token, str) or not 30 <= len(token) <= 128:
        return None
    try:
        hashed = _digest(token)
    except (UnicodeEncodeError, ValueError):
        return None
    with _ACCOUNT_LOCK, _db() as conn:
        row = conn.execute(
            """SELECT users.id,users.email,sessions.csrf_hash,sessions.expires_at
            FROM sessions JOIN users ON users.id=sessions.user_id
            WHERE token_hash=? AND expires_at>?""",
            (hashed, int(time.time())),
        ).fetchone()
        return dict(row) if row else None


def require_csrf(user, value):
    if user is None:
        raise PermissionError("Sign in required")
    if not isinstance(value, str) or len(value) > 128:
        raise PermissionError("Missing or invalid CSRF token")
    if not hmac.compare_digest(_digest(value), user["csrf_hash"]):
        raise PermissionError("Missing or invalid CSRF token")


def logout(token, user, csrf):
    require_csrf(user, csrf)
    with _ACCOUNT_LOCK, _db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (_digest(token),))


def _quantity(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"(?:0|[1-9]\d{0,22})(?:\.\d{1,18})?", raw):
        raise AccountError("Use a nonnegative decimal quantity (up to 18 decimal places)")
    try:
        amount = Decimal(raw)
    except InvalidOperation as exc:
        raise AccountError("Invalid coin quantity") from exc
    if not amount.is_finite() or amount < 0 or amount > Decimal("1e23"):
        raise AccountError("Coin quantity is outside allowed range")
    return format(amount.normalize(), "f")


def list_holdings(user):
    if user is None:
        raise PermissionError("Sign in required")
    with _ACCOUNT_LOCK, _db() as conn:
        rows = conn.execute("SELECT asset_id,quantity,updated_at FROM holdings WHERE user_id=? ORDER BY updated_at DESC",
                            (user["id"],)).fetchall()
    return {"holdings": [dict(row) for row in rows], "source": "Manually entered account records",
            "verified": False,
            "note": "User-entered amounts are not wallet balances or proof of ownership. Quotes are separate provider observations."}


def save_holding(user, csrf, asset_id, quantity):
    require_csrf(user, csrf)
    if not isinstance(asset_id, str) or not _COIN.fullmatch(asset_id):
        raise AccountError("Select a valid CoinGecko coin ID")
    amount = _quantity(quantity)
    with _ACCOUNT_LOCK, _db() as conn:
        existing = conn.execute("SELECT 1 FROM holdings WHERE user_id=? AND asset_id=?",
                                (user["id"],asset_id)).fetchone()
        if existing is None:
            count = conn.execute("SELECT count(*) FROM holdings WHERE user_id=?",
                                 (user["id"],)).fetchone()[0]
            if count >= _MAX_POSITIONS:
                raise AccountError("Maximum of 100 manually tracked assets reached")
        conn.execute("""INSERT INTO holdings(user_id,asset_id,quantity,updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(user_id,asset_id) DO UPDATE SET
            quantity=excluded.quantity,updated_at=excluded.updated_at""",
            (user["id"],asset_id,amount,int(time.time())))
    return {"asset_id": asset_id, "quantity": amount}


def delete_holding(user, csrf, asset_id):
    require_csrf(user, csrf)
    if not isinstance(asset_id, str) or not _COIN.fullmatch(asset_id):
        raise AccountError("Invalid coin ID")
    with _ACCOUNT_LOCK, _db() as conn:
        conn.execute("DELETE FROM holdings WHERE user_id=? AND asset_id=?",
                     (user["id"],asset_id))
