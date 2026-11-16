import os, tempfile, threading, unittest
from decimal import Decimal as D
from app import selfcheck
from app.db import connect
from app.schema import create_schema
from app.services import catalog, inventory, purchasing, sales


class TestSelfCheck(unittest.TestCase):
    def test_workflow_on_sqlite(self):
        done = selfcheck.run_on_url("sqlite:///x")
        self.assertGreaterEqual(len(done), 18)


class TestConcurrentSales(unittest.TestCase):
    """Two cash registers sell the LAST bottle at the same moment: exactly one may succeed."""

    def test_only_one_of_two_simultaneous_sales_gets_the_last_bottle(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            url = "sqlite:///" + os.path.join(tmp, "c.db").replace("\\", "/")
            db = connect(url); create_schema(db)
            oil = catalog.add_oil(db, "Oudh", "0.90"); sup = purchasing.add_supplier(db, "S")
            purchasing.buy_oil(db, sup, oil, "10.8", "g", 500, "2026-11-01")          # exactly one 12 ml bottle of oil
            purchasing.buy_bottles(db, sup, 12, 5, 200, "2026-11-01")
            pid = catalog.add_product(db, "Oudh 12ml", oil, 12, 1300)
            db.conn.close()
            results, start = [], threading.Barrier(2)

            def attempt():
                d = connect(url)
                try:
                    start.wait()
                    results.append(("ok", sales.sell(d, [{"product_id": pid, "qty": 1}], sold_on="2026-11-07")))
                except ValueError as e:
                    results.append(("refused", str(e)))
                finally:
                    d.conn.close()

            ts = [threading.Thread(target=attempt) for _ in range(2)]
            [t.start() for t in ts]; [t.join() for t in ts]
            self.assertEqual(sorted(r[0] for r in results), ["ok", "refused"], results)
            db = connect(url)
            self.assertEqual(inventory.get_stock(db, "oil", oil), D("0"))
            self.assertEqual(len(sales.list_sales(db)), 1)
            db.conn.close()


@unittest.skipUnless(os.environ.get("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run against a real PostgreSQL")
class TestRealPostgres(unittest.TestCase):
    """Runs the whole workflow, the concurrency test and the schema upgrade on a REAL PostgreSQL, inside a temporary schema."""

    def test_workflow_on_postgres(self):
        self.assertGreaterEqual(len(selfcheck.run_on_url(os.environ["TEST_POSTGRES_URL"])), 18)

    def test_concurrent_last_bottle_on_postgres(self):
        import uuid
        url = os.environ["TEST_POSTGRES_URL"]
        schema = "azeem_conc_" + uuid.uuid4().hex[:8]

        def open_db():
            d = connect(url)
            d.execute(f"SET search_path TO {schema}"); d.conn.commit()
            return d
        admin = connect(url)
        admin.execute(f"CREATE SCHEMA {schema}"); admin.conn.commit()
        try:
            db = open_db(); create_schema(db)
            oil = catalog.add_oil(db, "Oudh", "0.90"); sup = purchasing.add_supplier(db, "S")
            purchasing.buy_oil(db, sup, oil, "10.8", "g", 500, "2026-11-01")
            purchasing.buy_bottles(db, sup, 12, 5, 200, "2026-11-01")
            pid = catalog.add_product(db, "Oudh 12ml", oil, 12, 1300)
            db.conn.close()
            results, start = [], threading.Barrier(2)

            def attempt():
                d = open_db()
                try:
                    start.wait()
                    results.append(("ok", sales.sell(d, [{"product_id": pid, "qty": 1}], sold_on="2026-11-07")))
                except ValueError as e:
                    results.append(("refused", str(e)))
                finally:
                    d.conn.close()
            ts = [threading.Thread(target=attempt) for _ in range(2)]
            [t.start() for t in ts]; [t.join() for t in ts]
            self.assertEqual(sorted(r[0] for r in results), ["ok", "refused"], results)
        finally:
            admin.conn.rollback()
            admin.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE"); admin.conn.commit(); admin.conn.close()


if __name__ == "__main__":
    unittest.main()
