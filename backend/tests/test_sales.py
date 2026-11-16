import unittest
from decimal import Decimal as D
from tests.helpers import fresh_db
from app.services import catalog, purchasing, inventory, sales


class TestSales(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.oil = catalog.add_oil(self.db, "Oudh", "0.90")
        sup = purchasing.add_supplier(self.db, "Haji")
        purchasing.buy_oil(self.db, sup, self.oil, 1, "kg", 50000, "2026-11-01")      # 1000 g @ 50/g
        purchasing.buy_bottles(self.db, sup, 6, 10, 300, "2026-11-01")                 # 10 x 6ml @ 30
        purchasing.buy_bottles(self.db, sup, 12, 10, 400, "2026-11-01")                # 10 x 12ml @ 40
        self.p6 = catalog.add_product(self.db, "Oudh 6ml", self.oil, 6, 700)
        self.p12 = catalog.add_product(self.db, "Oudh 12ml", self.oil, 12, 1300)

    def stock(self):
        return inventory.get_stock(self.db, "oil", self.oil)

    def test_sale_deducts_oil_and_bottles_and_totals(self):
        sid = sales.sell(self.db, [{"product_id": self.p6, "qty": 1}, {"product_id": self.p12, "qty": 2}],
                         "Ali", "cash", 100, "2026-11-07")
        s = sales.get_sale(self.db, sid)
        self.assertEqual(s["invoice_no"], f"INV-{sid:06d}")
        self.assertEqual((s["subtotal"], s["discount"], s["total"]), ("3300.00", "100.00", "3200.00"))
        self.assertEqual(self.stock(), D("1000") - D("5.4") - D("21.6"))               # density 0.9, not 1 g/ml
        self.assertEqual(inventory.get_stock(self.db, "bottle", self.db.one("SELECT id FROM bottles WHERE size_ml=6")["id"]), D("9"))
        # cost: oil 27 g * 50 = 1350 ; bottles 1*30 + 2*40 = 110 -> 1460
        self.assertEqual(s["cost_total"], "1460.00")

    def test_insufficient_oil_blocks_whole_sale_and_changes_nothing(self):
        inventory.stocktake(self.db, "oil", self.oil, 20)       # only 20 g left
        with self.assertRaises(ValueError) as cm:
            # first line (5.4 g) fits, second (21.6 g) does not -> the first deduction must be undone too
            sales.sell(self.db, [{"product_id": self.p6, "qty": 1}, {"product_id": self.p12, "qty": 2}], sold_on="2026-11-07")
        self.assertIn("Oudh 12ml", str(cm.exception))
        self.assertEqual(self.stock(), D("20.000"))
        b6 = self.db.one("SELECT id FROM bottles WHERE size_ml=6")["id"]
        self.assertEqual(inventory.get_stock(self.db, "bottle", b6), D("10"))
        self.assertEqual(sales.list_sales(self.db), [])

    def test_insufficient_bottles_blocks_sale(self):
        with self.assertRaises(ValueError):
            sales.sell(self.db, [{"product_id": self.p6, "qty": 11}], sold_on="2026-11-07")
        self.assertEqual(self.stock(), D("1000.000"))

    def test_bottle_shortage_message_is_in_bottles_not_grams(self):
        with self.assertRaises(ValueError) as cm:
            sales.sell(self.db, [{"product_id": self.p6, "qty": 11}], sold_on="2026-11-07")
        self.assertIn("bottles", str(cm.exception))
        self.assertNotIn(" g,", str(cm.exception))

    def test_same_product_twice_is_merged(self):
        sid = sales.sell(self.db, [{"product_id": self.p6, "qty": 1}, {"product_id": self.p6, "qty": 2}], sold_on="2026-11-07")
        s = sales.get_sale(self.db, sid)
        self.assertEqual(len(s["items"]), 1); self.assertEqual(s["items"][0]["qty"], 3)

    def test_validation(self):
        bad = [dict(items=[]), dict(items=[{"product_id": self.p6, "qty": 0}]),
               dict(items=[{"product_id": self.p6, "qty": "1.5"}]), dict(items=[{"product_id": 999, "qty": 1}]),
               dict(items=[{"product_id": self.p6, "qty": 1}], discount=-1),
               dict(items=[{"product_id": self.p6, "qty": 1}], discount=701),
               dict(items=[{"product_id": self.p6, "qty": 1}], payment_method="barter")]
        for kw in bad:
            with self.assertRaises(ValueError, msg=str(kw)):
                sales.sell(self.db, sold_on="2026-11-07", **kw)
        self.assertEqual(self.stock(), D("1000.000"))

    def test_void_restores_stock_and_cannot_repeat(self):
        sid = sales.sell(self.db, [{"product_id": self.p12, "qty": 2}], sold_on="2026-11-07")
        sales.void_sale(self.db, sid, "customer returned")
        self.assertEqual(self.stock(), D("1000.000"))
        self.assertEqual(sales.get_sale(self.db, sid)["voided"], 1)
        with self.assertRaises(ValueError):
            sales.void_sale(self.db, sid)
        kinds = [r["kind"] for r in inventory.ledger(self.db, "oil", self.oil)]
        self.assertEqual(kinds, ["purchase", "sale", "sale_void"])

    def test_missing_sale(self):
        with self.assertRaises(sales.NotFound):
            sales.get_sale(self.db, 999)

    def test_price_change_does_not_alter_old_sale(self):
        sid = sales.sell(self.db, [{"product_id": self.p6, "qty": 1}], sold_on="2026-11-07")
        catalog.set_price(self.db, self.p6, 999)
        self.assertEqual(sales.get_sale(self.db, sid)["items"][0]["unit_price"], "700")


if __name__ == "__main__":
    unittest.main()
