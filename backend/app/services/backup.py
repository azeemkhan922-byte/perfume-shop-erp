"""Whole-database backup to one JSON file, and restore from it.
The file holds EVERYTHING including the owner's password hash: keep it private."""
import json

from app.db import now
from app.schema import schema_version

# parents before children (restore inserts in this order, deletes in reverse)
TABLE_ORDER = ["owner", "settings", "oils", "bottles", "supplies", "products", "product_supplies", "suppliers",
               "customers", "purchases", "supplier_payments", "batches", "stock_movements", "sales", "sale_items",
               "expenses"]
IDENTITY_TABLES = [t for t in TABLE_ORDER if t not in ("owner", "settings")]
FORMAT = 1


class BackupError(ValueError):
    pass


def _columns(db, table):
    cur = db.execute(f"SELECT * FROM {table} LIMIT 0")
    return [getattr(d, "name", None) or d[0] for d in cur.description]


def export_all(db) -> dict:
    return {"app": "azeem-erp", "format": FORMAT, "schema_version": schema_version(db), "created_at": now(),
            "tables": {t: db.query(f"SELECT * FROM {t}") for t in TABLE_ORDER}}


def export_json(db) -> bytes:
    return json.dumps(export_all(db), ensure_ascii=False, indent=1).encode("utf-8")


def _validate(db, data):
    if not isinstance(data, dict) or data.get("app") != "azeem-erp" or data.get("format") != FORMAT:
        raise BackupError("this is not an AZEEM ERP backup file")
    if data.get("schema_version") != schema_version(db):
        raise BackupError(f"backup is from database version {data.get('schema_version')}, this app is version "
                          f"{schema_version(db)}; restore it with the matching app version")
    tables = data.get("tables")
    if not isinstance(tables, dict) or set(tables) != set(TABLE_ORDER):
        raise BackupError("backup is incomplete or has unexpected tables")
    for t in TABLE_ORDER:
        cols = set(_columns(db, t))
        if not isinstance(tables[t], list):
            raise BackupError(f"table {t} is malformed")
        for row in tables[t]:
            if not isinstance(row, dict) or not set(row) <= cols:
                raise BackupError(f"table {t} has unknown columns")
    if len(tables["owner"]) != 1:
        raise BackupError("backup must contain exactly one owner account")


def restore(db, data) -> dict:
    """Replace ALL current data with the backup. All-or-nothing: any problem leaves the current data untouched."""
    _validate(db, data)
    tables = data["tables"]
    with db.tx():
        for t in reversed(TABLE_ORDER):
            db.execute(f"DELETE FROM {t}")
        for t in TABLE_ORDER:
            for row in tables[t]:
                names = list(row)
                db.execute(f"INSERT INTO {t} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",
                           [row[n] for n in names])
        if db.dialect == "postgres":  # identity counters must continue after the highest restored id
            for t in IDENTITY_TABLES:
                db.execute(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), COALESCE((SELECT MAX(id) FROM {t}), 1), "
                           f"(SELECT MAX(id) FROM {t}) IS NOT NULL)")
    return {t: len(tables[t]) for t in TABLE_ORDER}


def restore_json(db, raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        raise BackupError("the file is not valid JSON")
    return restore(db, data)
