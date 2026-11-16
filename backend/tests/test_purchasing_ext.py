import unittest
from decimal import Decimal as D
from tests.helpers import fresh_db
from app.services import catalog, purchasing, inventory


class TestLandedCostAndPayments(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.oil = catalog.add_oil(self.db, "Oudh", "0.90")
        self.sup = purchasing.add_supplier(self.db, "Haji")
        self.b12 = self.db.one("SELECT id FROM bottles WHERE size_ml=12")["id"]

    def test_transport_is_added_to_cost_per_gram(self):
        purchasing.buy_oil(self.db, self.sup, self.oil, 1, "kg", 50000, "2026-11-01", transport_charge=1000)
        self.assertEqual(self.db.one("SELECT avg_cost_per_g a FROM oils")["a"], "51.0000")
        p = purchasing.list_purchases(self.db)[0]
        self.assertEqual((p["total_price"], p["transport_charge"], p["landed_total"], p["rate"]), ("50000", "1000", "51000", "50000.00"))  # rate = per unit entered (per kg here)
        self.assertEqual((p["supplier_name"], p["item_name"]), ("Haji", "Oudh"))

    def test_negative_transport_rejected(self):
        with self.assertRaises(ValueError):
            purchasing.buy_oil(self.db, self.sup, self.oil, 1, "kg", 100, "2026-11-01", transport_charge=-1)
        self.assertEqual(purchasing.list_purchases(self.db), [])

    def test_supply_purchase_updates_stock_and_cost(self):
        cap = catalog.add_supply(self.db, "cap", "Gold cap")
        purchasing.buy_supply(self.db, self.sup, cap, 100, 500, "2026-11-01", transport_charge=50)
        s = self.db.one("SELECT * FROM supplies")
        self.assertEqual((s["stock_qty"], s["avg_cost_each"]), ("100", "5.5000"))
        with self.assertRaises(ValueError):
            purchasing.buy_supply(self.db, self.sup, cap, "1.5", 5, "2026-11-01")

    def test_invoice_shares_transport_and_updates_all_stock(self):
        cap = catalog.add_supply(self.db, "cap", "Gold cap")
        ids = purchasing.record_purchase_invoice(self.db, self.sup, "SUP-77", "2026-11-02", [
            {"kind": "oil", "item_id": self.oil, "qty": 1, "unit": "kg", "total_price": 50000},
            {"kind": "bottle", "item_id": self.b12, "qty": 10, "total_price": 400},
            {"kind": "supply", "item_id": cap, "qty": 10, "total_price": 50},
        ], transport_charge=510)
        rows = purchasing.list_purchases(self.db)
        self.assertEqual(len(ids), 3)
        self.assertTrue(all(r["invoice_no"] == "SUP-77" for r in rows))
        self.assertEqual(sum(D(r["transport_charge"]) for r in rows), D("510"))          # nothing lost to rounding
        self.assertEqual(sum(D(r["landed_total"]) for r in rows), D("50450") + D("510"))
        self.assertEqual(inventory.get_stock(self.db, "oil", self.oil), D("1000"))
        self.assertEqual(inventory.get_stock(self.db, "bottle", self.b12), D("10"))
        self.assertEqual(inventory.get_stock(self.db, "supply", cap), D("10"))

    def test_invoice_is_all_or_nothing(self):
        with self.assertRaises(ValueError):
            purchasing.record_purchase_invoice(self.db, self.sup, "X", "2026-11-02", [
                {"kind": "oil", "item_id": self.oil, "qty": 1, "unit": "kg", "total_price": 50000},
                {"kind": "gold", "item_id": 1, "qty": 1, "total_price": 1}])
        self.assertEqual(purchasing.list_purchases(self.db), [])
        self.assertEqual(inventory.get_stock(self.db, "oil", self.oil), D("0"))
        with self.assertRaises(ValueError):
            purchasing.record_purchase_invoice(self.db, self.sup, "X", "2026-11-02", [])

    def test_payments_and_balance(self):
        purchasing.record_purchase_invoice(self.db, self.sup, "A1", "2026-11-02", [
            {"kind": "oil", "item_id": self.oil, "qty": 1, "unit": "kg", "total_price": 50000}],
            transport_charge=1000, paid_amount=20000, pay_method="upi")
        s = purchasing.supplier_summary(self.db)[0]
        self.assertEqual((s["total_purchased"], s["total_paid"], s["balance_due"]), ("51000.00", "20000.00", "31000.00"))
        purchasing.add_payment(self.db, self.sup, "31000", "2026-11-10", "cash", "settled")
        s = purchasing.supplier_summary(self.db)[0]
        self.assertEqual(s["balance_due"], "0.00")
        self.assertEqual(len(purchasing.list_payments(self.db, self.sup)), 2)

    def test_payment_validation(self):
        for amt, day, method, sup in ((0, "2026-11-10", "cash", self.sup), (-5, "2026-11-10", "cash", self.sup),
                                      (5, "10-11-2026", "cash", self.sup), (5, "2026-11-10", "gold", self.sup),
                                      (5, "2026-11-10", "cash", 999)):
            with self.assertRaises(ValueError):
                purchasing.add_payment(self.db, sup, amt, day, method)
        self.assertEqual(purchasing.list_payments(self.db), [])

    def test_update_supplier(self):
        purchasing.update_supplier(self.db, self.sup, name="Haji & Sons", phone="0301")
        s = purchasing.list_suppliers(self.db)[0]
        self.assertEqual((s["name"], s["phone"]), ("Haji & Sons", "0301"))
        with self.assertRaises(ValueError):
            purchasing.update_supplier(self.db, 999, name="x")


if __name__ == "__main__":
    unittest.main()
