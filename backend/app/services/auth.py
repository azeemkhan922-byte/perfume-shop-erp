"""Single-owner authentication. Signed, expiring tokens; lockout after repeated failures."""
import base64, hashlib, hmac, json, time
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password, verify_password

MAX_FAILS, LOCK_MINUTES = 5, 15


class AuthError(Exception):
    pass


def _utc():
    return datetime.now(timezone.utc)


def create_owner(db, username: str, password: str):
    if db.one("SELECT id FROM owner WHERE id=1"):
        raise AuthError("owner already exists")
    if not username.strip():
        raise ValueError("username required")
    with db.tx():
        db.insert("owner", id=1, username=username.strip(), password_hash=hash_password(password))


def change_password(db, old: str, new: str):
    o = db.one("SELECT * FROM owner WHERE id=1")
    if not o or not verify_password(old, o["password_hash"]):
        raise AuthError("wrong current password")
    with db.tx():
        db.execute("UPDATE owner SET password_hash=? WHERE id=1", (hash_password(new),))


def _sign(payload: bytes, secret: str) -> str:
    return base64.urlsafe_b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()).decode()


def make_token(secret: str, hours: int, now=None) -> str:
    if len(secret) < 32:
        raise ValueError("SECRET_KEY must be at least 32 characters")
    exp = int((now if now is not None else time.time()) + hours * 3600)
    body = base64.urlsafe_b64encode(json.dumps({"sub": "owner", "exp": exp}).encode())
    return body.decode() + "." + _sign(body, secret)


def verify_token(token: str, secret: str, now=None) -> bool:
    try:
        body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(body.encode(), secret)):
            return False
        data = json.loads(base64.urlsafe_b64decode(body))
        return data.get("sub") == "owner" and data["exp"] > (now if now is not None else time.time())
    except Exception:
        return False


def login(db, username: str, password: str, secret: str, hours: int) -> str:
    o = db.one("SELECT * FROM owner WHERE id=1")
    if not o:
        raise AuthError("invalid credentials")
    if o["locked_until"] and datetime.fromisoformat(o["locked_until"]) > _utc():
        raise AuthError("too many attempts, try again later")
    ok = hmac.compare_digest(username, o["username"]) and verify_password(password, o["password_hash"])
    with db.tx():
        if ok:
            db.execute("UPDATE owner SET failed_logins=0, locked_until=NULL WHERE id=1")
        else:
            fails = o["failed_logins"] + 1
            lock = (_utc() + timedelta(minutes=LOCK_MINUTES)).isoformat() if fails >= MAX_FAILS else None
            db.execute("UPDATE owner SET failed_logins=?, locked_until=? WHERE id=1", (0 if lock else fails, lock))
    if not ok:
        raise AuthError("invalid credentials")
    return make_token(secret, hours)


def confirm_password(db, password: str) -> bool:
    """Re-check the owner's password for dangerous actions (restore). Does not touch lockout counters."""
    o = db.one("SELECT password_hash FROM owner WHERE id=1")
    return bool(o) and verify_password(password or "", o["password_hash"])
