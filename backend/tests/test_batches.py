import unittest
from decimal import Decimal as D
from tests.helpers import fresh_db, seed
from app.services import batches, catalog, inventory, purchasing


class TestBatches(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.s = seed(self.db)

    def oil(self): return inventory.get_stock(self.db, "oil", self.s["oil"])
    def b12(self): return inventory.get_stock(self.db, "bottle", self.db.one("SELECT id FROM bottles WHERE size_ml=12")["id"])
    def prod(self): return self.db.one("SELECT * FROM products WHERE id=?", (self.s["p12"],))

    def test_batch_cost_wastage_and_finished_stock(self):
        # 10 x 12 ml Oudh: 10 x 10.8 g = 108 g + 2 g wastage = 110 g @ Rs 50 = 5500; bottles 10 x 40 = 400; other 100 -> 6000
        bid = batches.make_batch(self.db, self.s["p12"], 10, wastage_g=2, other_cost=100, made_on="2026-11-05")
        b = batches.list_batches(self.db)[0]
        self.assertEqual((b["id"], b["units"], b["oil_grams_used"], b["wastage_g"], b["wastage_cost"], b["total_cost"], b["unit_cost"]),
                         (bid, 10, "110.000", "2.000", "100.00", "6000.00", "600.0000"))
        self.assertEqual(self.oil(), D("890")); self.assertEqual(self.b12(), D("20"))
        p = self.prod()
        self.assertEqual((p["stock_qty"], p["avg_cost_each"]), ("10", "600.0000"))
        kinds = [r["kind"] for r in inventory.ledger(self.db, "product", self.s["p12"])]
        self.assertEqual(kinds, ["batch"])

    def test_second_batch_averages_unit_cost(self):
        batches.make_batch(self.db, self.s["p12"], 10, wastage_g=2, other_cost=100)       # 600 each
        batches.make_batch(self.db, self.s["p12"], 10)                                     # 540 + 40 = 580 each
        self.assertEqual(self.prod()["avg_cost_each"], "590.0000")
        self.assertEqual(self.prod()["stock_qty"], "20")

    def test_components_are_consumed_and_costed(self):
        cap = catalog.add_supply(self.db, "cap", "Gold cap")
        purchasing.buy_supply(self.db, self.s["sup"], cap, 100, 500, "2026-11-01")         # 5 each
        catalog.set_product_supplies(self.db, self.s["p12"], [{"supply_id": cap, "qty": 1}])
        batches.make_batch(self.db, self.s["p12"], 10)                                      # 540 + 40 + 5 = 585
        self.assertEqual(inventory.get_stock(self.db, "supply", cap), D("90"))
        self.assertEqual(self.prod()["avg_cost_each"], "585.0000")

    def test_shortage_changes_nothing(self):
        cap = catalog.add_supply(self.db, "cap", "Gold cap")
        catalog.set_product_supplies(self.db, self.s["p12"], [{"supply_id": cap, "qty": 1}])   # no caps in stock
        with self.assertRaises(ValueError) as cm:
            batches.make_batch(self.db, self.s["p12"], 10)
        self.assertIn("Oudh 12ml", str(cm.exception))
        self.assertEqual((self.oil(), self.b12()), (D("1000"), D("30")))
        self.assertEqual(batches.list_batches(self.db), [])
        self.assertEqual(self.prod()["stock_qty"], "0")
        with self.assertRaises(ValueError):                                                     # 31 bottles > 30
            batches.make_batch(self.db, self.s["p12"], 31)
        self.assertEqual(self.oil(), D("1000"))

    def test_validation(self):
        for kw in (dict(units=0), dict(units="1.5"), dict(units=5, wastage_g=-1), dict(units=5, other_cost=-1)):
            with self.assertRaises(ValueError, msg=str(kw)):
                batches.make_batch(self.db, self.s["p12"], **kw)
        with self.assertRaises(ValueError):
            batches.make_batch(self.db, 999, 5)


if __name__ == "__main__":
    unittest.main()
