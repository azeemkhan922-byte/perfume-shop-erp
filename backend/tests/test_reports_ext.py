import unittest
from decimal import Decimal as D
from tests.helpers import fresh_db, seed
from app.services import batches, catalog, expenses, purchasing, reports, sales, settings


class TestReportsExt(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.s = seed(self.db)

    def test_revenue_excludes_tax(self):
        settings.set_many(self.db, {"tax_rate": "5"})
        sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 2}], discount=100, sold_on="2026-11-07")
        d = reports.daily_report(self.db, "2026-11-07")
        self.assertEqual((d["revenue"], d["tax_collected"], d["cost_of_goods"], d["gross_profit"]),
                         ("2500.00", "125.00", "1160.00", "1340.00"))
        expenses.add_expense(self.db, "2026-11-07", "Rent", 300)
        expenses.add_expense(self.db, "2026-11-07", "Rent", 200)
        expenses.add_expense(self.db, "2026-11-07", "Tea", 50)
        m = reports.monthly_report(self.db, "2026-11")
        self.assertEqual(m["net_profit"], "790.00")
        self.assertEqual(m["expenses_by_category"], [{"category": "Rent", "amount": "500.00"}, {"category": "Tea", "amount": "50.00"}])

    def test_stock_report_values_and_low_flags(self):
        r = reports.stock_report(self.db)
        by = {(i["type"], i["name"]): i for i in r["items"]}
        self.assertEqual(by[("oil", "Oudh")]["value"], "50000.00")
        self.assertEqual(by[("bottle", "12 ml bottle")]["value"], "1200.00")
        self.assertEqual(r["total_value"], "52100.00")
        self.assertFalse(by[("oil", "Oudh")]["low"])
        self.assertTrue(by[("bottle", "100 ml bottle")]["low"])                 # 0 in stock
        settings.set_many(self.db, {"low_stock_oil_g": "2000"})
        self.assertTrue({(i["type"], i["name"]): i for i in reports.stock_report(self.db)["items"]}[("oil", "Oudh")]["low"])

    def test_inventory_value_includes_finished_and_supplies(self):
        cap = catalog.add_supply(self.db, "cap", "Gold cap")
        purchasing.buy_supply(self.db, self.s["sup"], cap, 100, 500, "2026-11-01")
        batches.make_batch(self.db, self.s["p12"], 10)                           # 10 finished @ 580
        r = reports.stock_report(self.db)
        types = {i["type"] for i in r["items"]}
        self.assertTrue({"oil", "bottle", "cap", "finished"} <= types)
        # oil 892 g x 50 = 44600 ; 12ml bottles 20 x 40 = 800 ; 6ml 30 x 30 = 900 ; caps 500 ; finished 10 x 580 = 5800
        self.assertEqual(r["total_value"], "52600.00")

    def test_low_stock_list_and_best_sellers(self):
        rose = catalog.add_oil(self.db, "Rose", "0.85")
        purchasing.buy_oil(self.db, self.s["sup"], rose, 500, "g", 10000, "2026-11-01")
        pr = catalog.add_product(self.db, "Rose 12ml", rose, 12, 900)
        sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 2}, {"product_id": self.s["p6"], "qty": 1}, {"product_id": pr, "qty": 1}], sold_on="2026-11-07")
        b = reports.best_sellers(self.db, "2026-11-%")
        self.assertEqual([(x["fragrance"], x["qty"], x["revenue"]) for x in b], [("Oudh", 3, "3300.00"), ("Rose", 1, "900.00")])
        self.assertEqual(reports.best_sellers(self.db, "2026-10-%"), [])
        self.assertTrue(all(i["low"] for i in reports.low_stock(self.db)))

    def test_wastage_reported(self):
        batches.make_batch(self.db, self.s["p12"], 10, wastage_g=2, made_on="2026-11-05")
        m = reports.monthly_report(self.db, "2026-11")
        self.assertEqual((m["wastage_g"], m["wastage_cost"]), ("2.000", "100.00"))
        self.assertEqual(reports.monthly_report(self.db, "2026-10")["wastage_g"], "0.000")

    def test_dashboard_full_keeps_old_keys_and_adds_new(self):
        d = reports.dashboard_full(self.db)
        self.assertTrue({"today", "month", "oils", "bottles", "inventory_value", "low_stock", "best_sellers"} <= set(d))
        self.assertEqual(d["inventory_value"], "52100.00")


if __name__ == "__main__":
    unittest.main()
