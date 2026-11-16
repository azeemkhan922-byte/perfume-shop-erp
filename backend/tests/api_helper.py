import json, os, tempfile
from urllib.parse import parse_qsl, urlsplit

from app import config
from app.api import dispatch
from app.db import connect
from app.schema import create_schema
from app.services import auth

SECRET = "t" * 40
PASSWORD = "a-strong-password"


class Api:
    """Calls the real API layer (routing, auth, validation, error mapping) against a temporary SQLite file."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        config.DATABASE_URL = "sqlite:///" + os.path.join(self.tmp.name, "t.db")
        config.SECRET_KEY = SECRET
        db = connect(config.DATABASE_URL)
        create_schema(db)
        auth.create_owner(db, "azeem", PASSWORD)
        db.conn.close()
        self.token = None

    def close(self):
        self.tmp.cleanup()

    def call(self, method, url, body=None, token="auto", raw_body=None):
        u = urlsplit(url)
        data = raw_body if raw_body is not None else (json.dumps(body).encode() if body is not None else b"")
        tok = self.token if token == "auto" else token
        status, headers, content = dispatch(method, u.path, dict(parse_qsl(u.query)), data, f"Bearer {tok}" if tok else "")
        ctype = headers.get("Content-Type", "")
        return status, (json.loads(content) if ctype.startswith("application/json") else content), headers

    def login(self):
        st, out, _ = self.call("POST", "/api/login", {"username": "azeem", "password": PASSWORD}, token=None)
        assert st == 200, out
        self.token = out["token"]

    def ok(self, method, url, body=None):
        st, out, _ = self.call(method, url, body)
        assert st == 200, (method, url, st, out)
        return out
