"""PostgreSQL compatibility checks that do not need a real PostgreSQL server:
a fake psycopg-style connection returns rows as dicts (dict_row) and uses %s placeholders."""
import unittest
from app.db import Db


class FakeCursor:
    def __init__(self, conn): self.conn = conn
    def execute(self, sql, params=()): self.conn.log.append((sql, params))
    def fetchone(self): return self.conn.row
    def fetchall(self): return [self.conn.row]


class FakeConn:
    def __init__(self, row): self.row, self.log, self.commits, self.rollbacks = row, [], 0, 0
    def cursor(self): return FakeCursor(self)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


class TestPostgresCompat(unittest.TestCase):
    def test_insert_returns_id_from_dict_row(self):
        c = FakeConn({"id": 7}); db = Db(c, "postgres")
        self.assertEqual(db.insert("suppliers", name="A", phone="1"), 7)
        sql, params = c.log[0]
        self.assertIn("%s,%s", sql); self.assertNotIn("?", sql)
        self.assertTrue(sql.endswith("RETURNING id")); self.assertEqual(params, ("A", "1"))

    def test_insert_returns_id_from_tuple_row(self):
        self.assertEqual(Db(FakeConn((9,)), "postgres").insert("suppliers", name="A"), 9)

    def test_insert_without_row_is_an_error(self):
        with self.assertRaises(RuntimeError):
            Db(FakeConn(None), "postgres").insert("suppliers", name="A")

    def test_postgres_tx_commits_and_rolls_back(self):
        c = FakeConn({"id": 1}); db = Db(c, "postgres")
        with db.tx(): pass
        self.assertEqual((c.commits, c.rollbacks), (1, 0))
        with self.assertRaises(RuntimeError):
            with db.tx(): raise RuntimeError("x")
        self.assertEqual((c.commits, c.rollbacks), (1, 1))

    def test_write_transactions_take_the_advisory_lock_first(self):
        c = FakeConn({"id": 1}); db = Db(c, "postgres")
        with db.tx():
            db.insert("suppliers", name="A")
            with db.tx():                                   # nested: must not lock a second time
                db.insert("suppliers", name="B")
        sqls = [sql for sql, _ in c.log]
        self.assertEqual(sqls[0], "SELECT pg_advisory_xact_lock(727274)")
        self.assertEqual(sum("pg_advisory_xact_lock" in q for q in sqls), 1)
        self.assertEqual(c.commits, 1)

    def test_sqlite_does_not_use_the_postgres_lock(self):
        from tests.helpers import fresh_db
        db = fresh_db()
        with db.tx():
            db.insert("suppliers", name="A")

    def test_query_converts_dict_rows(self):
        self.assertEqual(Db(FakeConn({"id": 3}), "postgres").query("SELECT 1"), [{"id": 3}])


if __name__ == "__main__":
    unittest.main()
