"""Starts the real backend on port 8765 with a THROW-AWAY database and one test owner, serving frontend/dist.
Used only by e2e.mjs. Never uses your real data.   Run from anywhere:  python e2e/serve.py"""
import os, sys, tempfile
from pathlib import Path

backend = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend))
tmp = Path(tempfile.mkdtemp(prefix="azeem-e2e-"))
os.environ["DATABASE_URL"] = "sqlite:///" + (tmp / "e2e.db").as_posix()
os.environ["SECRET_KEY"] = "e2e-only-secret-key-e2e-only-secret-key"
os.environ["QUIET"] = "1"
os.environ.setdefault("FRONTEND_DIST", str(backend.parent / "frontend" / "dist"))

from app import config
from app.db import connect
from app.devserver import main
from app.schema import create_schema
from app.services import auth

db = connect(config.DATABASE_URL)
create_schema(db)
auth.create_owner(db, "azeem", "a-strong-password")
db.conn.close()
print("Test database:", tmp)
main(int(os.environ.get("E2E_PORT", "8765")))
