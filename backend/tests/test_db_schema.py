import unittest
from tests.helpers import fresh_db


class TestDb(unittest.TestCase):
    def test_default_bottle_sizes_seeded(self):
        db = fresh_db()
        sizes = [r["size_ml"] for r in db.query("SELECT size_ml FROM bottles ORDER BY size_ml")]
        self.assertEqual(sizes, [6, 12, 30, 50, 100])

    def test_schema_is_repeatable(self):
        from app.schema import create_schema
        db = fresh_db()
        create_schema(db)
        self.assertEqual(len(db.query("SELECT id FROM bottles")), 5)

    def test_rollback_on_error(self):
        db = fresh_db()
        with self.assertRaises(RuntimeError):
            with db.tx():
                db.insert("suppliers", name="A")
                raise RuntimeError("boom")
        self.assertEqual(db.query("SELECT id FROM suppliers"), [])

    def test_nested_tx_rolls_back_together(self):
        db = fresh_db()
        with self.assertRaises(RuntimeError):
            with db.tx():
                with db.tx():
                    db.insert("suppliers", name="A")
                raise RuntimeError("boom")
        self.assertEqual(db.query("SELECT id FROM suppliers"), [])

    def test_bad_url(self):
        from app.db import connect
        with self.assertRaises(ValueError):
            connect("mysql://x")


if __name__ == "__main__":
    unittest.main()
