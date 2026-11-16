import unittest
from tests.helpers import fresh_db, seed
from app.services import customers, sales


class TestCustomers(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.s = seed(self.db)

    def test_crud_and_search(self):
        a = customers.add_customer(self.db, "Ali Khan", "0300111")
        customers.add_customer(self.db, "Sara", "0321222")
        self.assertEqual(len(customers.list_customers(self.db)), 2)
        self.assertEqual([c["name"] for c in customers.list_customers(self.db, "ali")], ["Ali Khan"])
        self.assertEqual([c["name"] for c in customers.list_customers(self.db, "0321")], ["Sara"])
        customers.update_customer(self.db, a, phone="0300999", notes="VIP")
        self.assertEqual(customers.list_customers(self.db, "ali")[0]["phone"], "0300999")
        customers.update_customer(self.db, a, active=False)
        self.assertEqual(len(customers.list_customers(self.db)), 1)
        with self.assertRaises(ValueError):
            customers.add_customer(self.db, " ")
        with self.assertRaises(ValueError):
            customers.update_customer(self.db, 999, name="x")

    def test_totals_and_history_ignore_voided(self):
        c = customers.add_customer(self.db, "Ali")
        s1 = sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 1}], customer_id=c, sold_on="2026-11-07")
        s2 = sales.sell(self.db, [{"product_id": self.s["p6"], "qty": 1}], customer_id=c, sold_on="2026-11-08")
        sales.void_sale(self.db, s2)
        row = customers.list_customers(self.db)[0]
        self.assertEqual((row["sales_count"], row["total_spent"]), (1, "1300.00"))
        hist = customers.customer_history(self.db, c)
        self.assertEqual([h["id"] for h in hist], [s2, s1])
        with self.assertRaises(ValueError):
            customers.customer_history(self.db, 999)
        sale = sales.get_sale(self.db, s1)
        self.assertEqual((sale["customer_id"], sale["customer_name"]), (c, "Ali"))

    def test_sale_with_unknown_customer_rejected(self):
        with self.assertRaises(ValueError):
            sales.sell(self.db, [{"product_id": self.s["p12"], "qty": 1}], customer_id=999, sold_on="2026-11-07")


if __name__ == "__main__":
    unittest.main()
