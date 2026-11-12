"""Tiny database layer: same code runs on SQLite (local/tests) and PostgreSQL (cloud).
Decimals are stored as TEXT so no float rounding ever touches money or grams."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _first_value(row, key):
    """RETURNING id comes back as a tuple (sqlite/psycopg default) or a dict (psycopg dict_row)."""
    if row is None:
        raise RuntimeError("insert did not return an id")
    if isinstance(row, (tuple, list)):
        return row[0]
    return row[key]


class Db:
    def __init__(self, conn, dialect: str):
        self.conn, self.dialect, self._depth = conn, dialect, 0

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.dialect == "postgres" else sql

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(self._sql(sql), tuple(params))
        return cur

    def query(self, sql, params=()):
        cur = self.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def insert(self, table, **cols):
        names = ",".join(cols)
        marks = ",".join("?" for _ in cols)
        cur = self.execute(f"INSERT INTO {table} ({names}) VALUES ({marks}) RETURNING id", list(cols.values()))
        return _first_value(cur.fetchone(), "id")

    @contextmanager
    def tx(self):
        """All-or-nothing block. Nested use joins the outer transaction."""
        if self._depth > 0:
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
            return
        self._depth = 1
        if self.dialect == "sqlite":
            self.conn.execute("BEGIN IMMEDIATE")      # one writer at a time
        else:
            # PostgreSQL would let two simultaneous sales both read the same stock and both succeed.
            # This lock (released automatically at commit/rollback) makes write transactions queue up, like SQLite does.
            self.execute("SELECT pg_advisory_xact_lock(727274)")
        try:
            yield
            self.conn.commit() if self.dialect == "postgres" else self.conn.execute("COMMIT")
        except BaseException:
            self.conn.rollback() if self.dialect == "postgres" else self.conn.execute("ROLLBACK")
            raise
        finally:
            self._depth = 0


def connect(url: str) -> Db:
    if url.startswith("sqlite:///"):
        conn = sqlite3.connect(url[len("sqlite:///"):], isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return Db(conn, "sqlite")
    if url.startswith(("postgres://", "postgresql://")):
        import psycopg  # installed from requirements.txt; only needed for the cloud
        from psycopg.rows import dict_row
        return Db(psycopg.connect(url, row_factory=dict_row), "postgres")
    raise ValueError("DATABASE_URL must start with sqlite:/// or postgresql://")


def shop_today(offset_minutes: int = 330) -> str:
    """Today's date (YYYY-MM-DD) in the shop's local time."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).date().isoformat()
