"""Command line tools:
  python -m app.cli create-owner              create the single owner account
  python -m app.cli backup  [file.json]       save a full backup (default: azeem-backup-DATE.json)
  python -m app.cli restore file.json         replace ALL data with a backup (asks to confirm)"""
import getpass, sys
from datetime import date

from app import config
from app.db import connect
from app.schema import create_schema
from app.services import auth, backup

USAGE = __doc__


def create_owner(db):
    user = input("Owner username: ").strip()
    pw = getpass.getpass("Password (10+ characters): ")
    if pw != getpass.getpass("Repeat password: "):
        print("Passwords do not match.")
        return 1
    try:
        auth.create_owner(db, user, pw)
    except (ValueError, auth.AuthError) as e:
        print("Error:", e)
        return 1
    print("Owner created.")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("create-owner", "backup", "restore"):
        print(USAGE)
        return 2
    db = connect(config.DATABASE_URL)
    create_schema(db)
    cmd = argv[0]
    if cmd == "create-owner":
        return create_owner(db)
    if cmd == "backup":
        path = argv[1] if len(argv) > 1 else f"azeem-backup-{date.today().isoformat()}.json"
        with open(path, "wb") as f:
            f.write(backup.export_json(db))
        print("Backup saved to", path)
        return 0
    if len(argv) < 2:
        print("usage: python -m app.cli restore file.json")
        return 2
    if input(f'This REPLACES all data in {config.DATABASE_URL.split("@")[-1]} with "{argv[1]}". Type RESTORE to continue: ') != "RESTORE":
        print("Cancelled.")
        return 1
    try:
        with open(argv[1], "rb") as f:
            counts = backup.restore_json(db, f.read())
    except (OSError, backup.BackupError) as e:
        print("Restore failed, nothing was changed:", e)
        return 1
    print("Restored:", ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
