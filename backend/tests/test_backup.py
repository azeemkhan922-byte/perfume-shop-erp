import json, unittest
from tests.helpers import fresh_db, seed
from app.services import auth, backup, batches, customers, expenses, purchasing, sales, settings


def populated():
    db = fresh_db()
    s = seed(db)
    auth.create_owner(db, "azeem", "a-strong-password")
    c = customers.add_customer(db, "Ali", "0300")
    settings.set_many(db, {"tax_rate": "5", "shop_phone": "0300"})
    batches.make_batch(db, s["p12"], 5, wastage_g=1, made_on="2026-11-05")
    sales.sell(db, [{"product_id": s["p12"], "qty": 7}], customer_id=c, sold_on="2026-11-07")
    expenses.add_expense(db, "2026-11-07", "Rent", 500)
    purchasing.add_payment(db, s["sup"], 1000, "2026-11-08")
    return db, s


def strip(d):
    d = dict(d); d.pop("created_at"); return d


class TestBackup(unittest.TestCase):
    def test_roundtrip_into_a_fresh_database(self):
        db, _ = populated()
        raw = backup.export_json(db)
        fresh = fresh_db()
        counts = backup.restore_json(fresh, raw)
        self.assertEqual(counts["sales"], 1)
        self.assertEqual(strip(backup.export_all(fresh)), strip(json.loads(raw)))
        self.assertTrue(auth.verify_token(auth.login(fresh, "azeem", "a-strong-password", "k" * 40, 1), "k" * 40))   # owner restored

    def test_restore_reverts_later_changes(self):
        db, s = populated()
        raw = backup.export_json(db)
        sales.sell(db, [{"product_id": s["p6"], "qty": 3}], sold_on="2026-11-09")
        expenses.add_expense(db, "2026-11-09", "Tea", 5)
        backup.restore_json(db, raw)
        self.assertEqual(len(sales.list_sales(db)), 1)
        self.assertEqual(len(expenses.list_expenses(db)), 1)

    def test_new_records_continue_after_highest_restored_id(self):
        db, s = populated()
        fresh = fresh_db()
        backup.restore_json(fresh, backup.export_json(db))
        new_id = purchasing.add_supplier(fresh, "Another")
        self.assertGreater(new_id, s["sup"])
        self.assertEqual(sales.sell(fresh, [{"product_id": s["p6"], "qty": 1}], sold_on="2026-11-09"), 2)

    def test_rejects_bad_files_and_keeps_data(self):
        db, _ = populated()
        good = backup.export_all(db)
        def mutated(fn):
            d = json.loads(json.dumps(good)); fn(d); return json.dumps(d).encode()
        bad = {
            "not json": b"{{{",
            "wrong app": mutated(lambda d: d.update(app="other")),
            "wrong version": mutated(lambda d: d.update(schema_version=99)),
            "missing table": mutated(lambda d: d["tables"].pop("sales")),
            "unknown column": mutated(lambda d: d["tables"]["oils"][0].update(evil="x")),
            "no owner": mutated(lambda d: d["tables"].update(owner=[])),
            "list not dict": json.dumps([1, 2]).encode(),
        }
        for name, raw in bad.items():
            with self.assertRaises(backup.BackupError, msg=name):
                backup.restore_json(db, raw)
        self.assertEqual(len(sales.list_sales(db)), 1)

    def test_failure_midway_rolls_back_everything(self):
        db, _ = populated()
        good = backup.export_all(db)
        broken = json.loads(json.dumps(good))
        broken["tables"]["product_supplies"] = [{"id": 1, "product_id": 999, "supply_id": 999, "qty_per_unit": 1}]   # dangling references
        with self.assertRaises(Exception):
            backup.restore(db, broken)
        self.assertEqual(strip(backup.export_all(db)), strip(good))               # untouched, not half-restored


if __name__ == "__main__":
    unittest.main()
