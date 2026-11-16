import unittest
from decimal import Decimal as D
from tests.helpers import fresh_db, seed
from app.services import batches, catalog, inventory, purchasing, sales, settings


class TestSalesExt(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.s = seed(self.db)
        self.b12id = self.db.one("SELECT id FROM bottles WHERE size_ml=12")["id"]

    def oil(self): return inventory.get_stock(self.db, "oil", self.s["oil"])
    def b12(self): return inventory.get_stock(self.db, "bottle", self.b12id)
    def fin(self): return D(self.db.one("SELECT stock_qty q FROM products WHERE id=?", (self.s["p12"],))["q"])

    def test_tax_from_settings_and_override(self):
        settings.set_many(self.db, {"tax_rate": "5"})
        sid = sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 2}], discount=100, sold_on="2026-11-07")
        s = sales.get_sale(self.db, sid)
        self.assertEqual((s["subtotal"], s["discount"], s["tax_rate"], s["tax_amount"], s["total"]),
                         ("2600.00", "100.00", "5", "125.00", "2625.00"))
        sid2 = sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 1}], tax_rate=0, sold_on="2026-11-07")
        self.assertEqual(sales.get_sale(self.db, sid2)["total"], "1300.00")
        with self.assertRaises(ValueError):
            sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 1}], tax_rate=101, sold_on="2026-11-07")

    def test_finished_stock_used_first_then_raw(self):
        batches.make_batch(self.db, self.s["p12"], 10)                       # 10 finished units @ Rs 580
        self.assertEqual((self.oil(), self.b12(), self.fin()), (D("892"), D("20"), D("10")))
        sid = sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 12}], sold_on="2026-11-07")
        s = sales.get_sale(self.db, sid)
        it = s["items"][0]
        self.assertEqual((it["qty"], it["finished_qty"], it["oil_grams"]), (12, 10, "21.600"))
        # cost = 10 finished x 580 + 21.6 g x 50 + 2 bottles x 40
        self.assertEqual(s["cost_total"], "6960.00")
        self.assertEqual((self.oil(), self.b12(), self.fin()), (D("870.4"), D("18"), D("0")))

    def test_selling_only_finished_stock_does_not_touch_raw(self):
        batches.make_batch(self.db, self.s["p12"], 10)
        before = (self.oil(), self.b12())
        sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 4}], sold_on="2026-11-07")
        self.assertEqual((self.oil(), self.b12(), self.fin()), (before[0], before[1], D("6")))

    def test_void_restores_finished_raw_and_components_exactly(self):
        cap = catalog.add_supply(self.db, "cap", "Gold cap")
        purchasing.buy_supply(self.db, self.s["sup"], cap, 100, 500, "2026-11-01")
        catalog.set_product_supplies(self.db, self.s["p12"], [{"supply_id": cap, "qty": 1}])
        batches.make_batch(self.db, self.s["p12"], 10)
        snap = (self.oil(), self.b12(), self.fin(), inventory.get_stock(self.db, "supply", cap))
        sid = sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 13}], sold_on="2026-11-07")
        self.assertEqual(inventory.get_stock(self.db, "supply", cap), snap[3] - 3)       # 3 raw units used 3 caps
        sales.void_sale(self.db, sid)
        self.assertEqual((self.oil(), self.b12(), self.fin(), inventory.get_stock(self.db, "supply", cap)), snap)

    def test_components_deducted_and_costed_for_raw_sale(self):
        cap = catalog.add_supply(self.db, "cap", "Gold cap")
        purchasing.buy_supply(self.db, self.s["sup"], cap, 100, 500, "2026-11-01")
        catalog.set_product_supplies(self.db, self.s["p12"], [{"supply_id": cap, "qty": 1}])
        sid = sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 2}], sold_on="2026-11-07")
        self.assertEqual(inventory.get_stock(self.db, "supply", cap), D("98"))
        self.assertEqual(sales.get_sale(self.db, sid)["cost_total"], "1170.00")          # 2 x (540 + 40 + 5)

    def test_missing_component_blocks_sale_and_rolls_back(self):
        cap = catalog.add_supply(self.db, "cap", "Gold cap")                              # none in stock
        catalog.set_product_supplies(self.db, self.s["p12"], [{"supply_id": cap, "qty": 1}])
        with self.assertRaises(ValueError):
            sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 1}], sold_on="2026-11-07")
        self.assertEqual((self.oil(), self.b12()), (D("1000"), D("30")))
        self.assertEqual(sales.list_sales(self.db), [])


if __name__ == "__main__":
    unittest.main()
