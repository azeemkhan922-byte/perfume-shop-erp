import unittest
from decimal import Decimal as D
from tests.helpers import fresh_db
from app.db import connect
from app.schema import create_schema, migrate, schema_version
from app.services import settings


class TestMigrations(unittest.TestCase):
    def test_fresh_db_is_latest_version_with_new_tables(self):
        db = fresh_db()
        self.assertEqual(schema_version(db), 2)
        for t in ("supplies", "customers", "batches", "supplier_payments", "settings", "product_supplies"):
            db.query(f"SELECT * FROM {t}")

    def test_old_v1_database_upgrades_without_losing_data(self):
        db = connect("sqlite:///:memory:")
        create_schema(db, migrate_to_latest=False)           # the original (version 1) tables
        sid = db.insert("suppliers", name="Old Supplier")
        oid = db.insert("oils", name="Rose", density_g_per_ml="0.9")
        db.insert("purchases", supplier_id=sid, kind="oil", item_id=oid, qty="1", unit="kg", base_qty="1000.000",
                  total_price="50000", purchased_on="2026-10-01", created_at="x")
        migrate(db)
        self.assertEqual(schema_version(db), 2)
        row = db.one("SELECT * FROM purchases")
        self.assertEqual((row["total_price"], row["landed_total"], row["transport_charge"]), ("50000", "50000", "0"))
        self.assertEqual(db.one("SELECT name FROM oils")["name"], "Rose")
        migrate(db)                                           # running again changes nothing
        self.assertEqual(schema_version(db), 2)


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()

    def test_defaults(self):
        s = settings.get_all(self.db)
        self.assertEqual((s["shop_name"], s["tax_rate"], s["low_stock_oil_g"]), ("AZEEM FRAGRANCES", "0", "100"))

    def test_update_and_persist(self):
        s = settings.set_many(self.db, {"tax_rate": "5.50", "shop_phone": " 0300 ", "upi_id": "azeem@upi"})
        self.assertEqual((s["tax_rate"], s["shop_phone"], s["upi_id"]), ("5.5", "0300", "azeem@upi"))
        self.assertEqual(settings.get(self.db, "tax_rate"), "5.5")
        settings.set_many(self.db, {"tax_rate": "100"})
        self.assertEqual(settings.get(self.db, "tax_rate"), "100")           # not "1E+2"
        settings.set_many(self.db, {"tax_rate": "0"})
        self.assertEqual(settings.get(self.db, "tax_rate"), "0")

    def test_validation_and_atomic(self):
        for bad in ({"tax_rate": "101"}, {"tax_rate": "-1"}, {"tax_rate": "abc"}, {"low_stock_oil_g": "-5"},
                    {"nonsense": "x"}, {"shop_name": " "}):
            with self.assertRaises(ValueError, msg=str(bad)):
                settings.set_many(self.db, bad)
        with self.assertRaises(ValueError):
            settings.set_many(self.db, {"shop_phone": "1", "tax_rate": "999"})
        self.assertEqual(settings.get(self.db, "shop_phone"), "")             # nothing half-saved


if __name__ == "__main__":
    unittest.main()
