import unittest
from tests.helpers import fresh_db
from app.services import catalog, purchasing, sales, expenses, reports


class TestReports(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        oil = catalog.add_oil(self.db, "Oudh", "0.90")
        sup = purchasing.add_supplier(self.db, "Haji")
        purchasing.buy_oil(self.db, sup, oil, 1, "kg", 50000, "2026-11-01")
        purchasing.buy_bottles(self.db, sup, 12, 50, 2000, "2026-11-01")   # 40 each
        self.p = catalog.add_product(self.db, "Oudh 12ml", oil, 12, 1300)  # cost: 10.8*50=540 + 40 = 580

    def test_daily_and_monthly_profit(self):
        sales.sell(self.db, [{"product_id": self.p, "qty": 2}], sold_on="2026-11-07")   # rev 2600 cost 1160
        sales.sell(self.db, [{"product_id": self.p, "qty": 1}], discount=100, sold_on="2026-11-08")  # rev 1200 cost 580
        expenses.add_expense(self.db, "2026-11-07", "Rent", 500)
        expenses.add_expense(self.db, "2026-11-20", "Electricity", "200.50")
        d = reports.daily_report(self.db, "2026-11-07")
        self.assertEqual((d["revenue"], d["cost_of_goods"], d["gross_profit"], d["expenses"], d["net_profit"]),
                         ("2600.00", "1160.00", "1440.00", "500.00", "940.00"))
        m = reports.monthly_report(self.db, "2026-11")
        self.assertEqual((m["sales_count"], m["revenue"], m["gross_profit"], m["expenses"], m["net_profit"]),
                         (2, "3800.00", "2060.00", "700.50", "1359.50"))
        self.assertEqual(m["discounts"], "100.00"); self.assertEqual(m["items_sold"], 3)
        self.assertEqual([x["day"] for x in m["by_day"]], ["2026-11-07", "2026-11-08", "2026-11-20"])
        self.assertEqual(m["top_products"][0], {"name": "Oudh 12ml", "qty": 3})

    def test_voided_sale_excluded(self):
        sid = sales.sell(self.db, [{"product_id": self.p, "qty": 1}], sold_on="2026-11-07")
        sales.void_sale(self.db, sid)
        d = reports.daily_report(self.db, "2026-11-07")
        self.assertEqual((d["sales_count"], d["revenue"], d["net_profit"]), (0, "0.00", "0.00"))

    def test_other_month_not_included(self):
        sales.sell(self.db, [{"product_id": self.p, "qty": 1}], sold_on="2026-10-31")
        self.assertEqual(reports.monthly_report(self.db, "2026-11")["revenue"], "0.00")

    def test_empty_period_and_bad_dates(self):
        self.assertEqual(reports.daily_report(self.db, "2026-01-01")["net_profit"], "0.00")
        with self.assertRaises(ValueError):
            reports.daily_report(self.db, "07-11-2026")
        with self.assertRaises(ValueError):
            reports.monthly_report(self.db, "2026-13")

    def test_expense_validation_list_delete(self):
        with self.assertRaises(ValueError):
            expenses.add_expense(self.db, "2026-11-07", "Rent", 0)
        with self.assertRaises(ValueError):
            expenses.add_expense(self.db, "yesterday", "Rent", 5)
        with self.assertRaises(ValueError):
            expenses.add_expense(self.db, "2026-11-07", " ", 5)
        i = expenses.add_expense(self.db, "2026-11-07", "Rent", 5)
        self.assertEqual(len(expenses.list_expenses(self.db, "2026-11")), 1)
        expenses.delete_expense(self.db, i)
        self.assertEqual(expenses.list_expenses(self.db), [])

    def test_dashboard_shape(self):
        d = reports.dashboard(self.db)
        self.assertEqual(set(d), {"today", "month", "oils", "bottles"})
        self.assertEqual(d["oils"][0]["stock_g"], "1000.000")


if __name__ == "__main__":
    unittest.main()
