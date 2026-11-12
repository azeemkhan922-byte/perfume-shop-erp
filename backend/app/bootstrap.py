"""First-run helpers for hosts without a shell (e.g. Render Free)."""
import os

from app.services import auth


def ensure_owner_from_env(db, environ=None) -> bool:
    """If there is NO owner yet and OWNER_USERNAME + OWNER_PASSWORD are set, create the owner.
    Does nothing once an owner exists. After the first start, delete these two variables from the host."""
    env = os.environ if environ is None else environ
    user, pw = env.get("OWNER_USERNAME", "").strip(), env.get("OWNER_PASSWORD", "")
    if not user or not pw or db.one("SELECT id FROM owner WHERE id=1"):
        return False
    auth.create_owner(db, user, pw)
    return True
