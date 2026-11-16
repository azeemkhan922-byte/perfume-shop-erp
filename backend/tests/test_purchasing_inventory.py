import unittest
from decimal import Decimal as D
from tests.helpers import fresh_db
from app.services import catalog, purchasing, inventory


class TestPurchasingInventory(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.oil = catalog.add_oil(self.db, "Oudh", "0.90")
        self.sup = purchasing.add_supplier(self.db, "Haji & Sons", "0300")

    def test_1kg_purchase_adds_1000g_and_cost(self):
        purchasing.buy_oil(self.db, self.sup, self.oil, 1, "kg", 50000, "2026-11-01")
        self.assertEqual(inventory.get_stock(self.db, "oil", self.oil), D("1000.000"))
        self.assertEqual(self.db.one("SELECT avg_cost_per_g a FROM oils")["a"], "50.0000")

    def test_second_purchase_averages_cost(self):
        purchasing.buy_oil(self.db, self.sup, self.oil, 1, "kg", 50000, "2026-11-01")
        purchasing.buy_oil(self.db, self.sup, self.oil, 500, "g", 40000, "2026-11-02")
        self.assertEqual(inventory.get_stock(self.db, "oil", self.oil), D("1500.000"))
        self.assertEqual(self.db.one("SELECT avg_cost_per_g a FROM oils")["a"], "60.0000")

    def test_ml_purchase_uses_density(self):
        purchasing.buy_oil(self.db, self.sup, self.oil, 100, "ml", 9000, "2026-11-01")
        self.assertEqual(inventory.get_stock(self.db, "oil", self.oil), D("90.000"))

    def test_bottle_purchase(self):
        purchasing.buy_bottles(self.db, self.sup, 12, 100, 3000, "2026-11-01")
        b = self.db.one("SELECT * FROM bottles WHERE size_ml=12")
        self.assertEqual(b["stock_qty"], "100")
        self.assertEqual(b["avg_cost_each"], "30.0000")

    def test_bottle_qty_must_be_whole(self):
        with self.assertRaises(ValueError):
            purchasing.buy_bottles(self.db, self.sup, 12, "2.5", 100, "2026-11-01")

    def test_failed_purchase_changes_nothing(self):
        with self.assertRaises(ValueError):
            purchasing.buy_oil(self.db, self.sup, self.oil, 1, "stone", 100, "2026-11-01")
        with self.assertRaises(ValueError):
            purchasing.buy_oil(self.db, 999, self.oil, 1, "kg", 100, "2026-11-01")
        self.assertEqual(inventory.get_stock(self.db, "oil", self.oil), D("0.000"))
        self.assertEqual(purchasing.list_purchases(self.db), [])

    def test_ledger_written_for_each_change(self):
        purchasing.buy_oil(self.db, self.sup, self.oil, 1, "kg", 50000, "2026-11-01")
        inventory.change_stock(self.db, "oil", self.oil, "-5.400", "sale")
        rows = inventory.ledger(self.db, "oil", self.oil)
        self.assertEqual([r["kind"] for r in rows], ["purchase", "sale"])
        self.assertEqual(rows[-1]["balance"], "994.600")

    def test_cannot_go_negative_and_nothing_logged(self):
        with self.assertRaises(ValueError):
            inventory.change_stock(self.db, "oil", self.oil, "-1", "sale")
        self.assertEqual(inventory.ledger(self.db, "oil", self.oil), [])

    def test_stocktake_records_difference(self):
        purchasing.buy_oil(self.db, self.sup, self.oil, 100, "g", 5000, "2026-11-01")
        inventory.stocktake(self.db, "oil", self.oil, "97.5")
        self.assertEqual(inventory.get_stock(self.db, "oil", self.oil), D("97.500"))
        self.assertEqual(inventory.ledger(self.db, "oil", self.oil)[-1]["delta"], "-2.500")
        with self.assertRaises(inventory.StockError):
            inventory.stocktake(self.db, "oil", self.oil, -1)

    def test_unknown_item(self):
        with self.assertRaises(inventory.StockError):
            inventory.get_stock(self.db, "oil", 999)


if __name__ == "__main__":
    unittest.main()
