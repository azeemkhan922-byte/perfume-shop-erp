import unittest
from decimal import Decimal as D
from tests.helpers import fresh_db
from app.services import catalog


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.oil = catalog.add_oil(self.db, "Oudh", "0.90")

    def test_oil_needs_positive_density_and_unique_name(self):
        with self.assertRaises(ValueError):
            catalog.add_oil(self.db, "Rose", 0)
        with self.assertRaises(Exception):
            catalog.add_oil(self.db, "Oudh", "0.9")

    def test_product_grams_use_density_not_1g_per_ml(self):
        p = catalog.add_product(self.db, "Oudh 12ml", self.oil, 12, 1500)
        self.assertEqual(catalog.oil_grams_needed(self.db, p), D("10.800"))

    def test_density_change_changes_grams(self):
        p = catalog.add_product(self.db, "Oudh 12ml", self.oil, 12, 1500)
        catalog.set_density(self.db, self.oil, "0.95")
        self.assertEqual(catalog.oil_grams_needed(self.db, p), D("11.400"))

    def test_diluted_product(self):
        p = catalog.add_product(self.db, "Oudh 12ml 25%", self.oil, 12, 800, "0.25")
        self.assertEqual(catalog.oil_grams_needed(self.db, p), D("2.700"))

    def test_product_validation(self):
        with self.assertRaises(ValueError):
            catalog.add_product(self.db, "X", 999, 12, 100)
        with self.assertRaises(ValueError):
            catalog.add_product(self.db, "X", self.oil, 7, 100)
        with self.assertRaises(ValueError):
            catalog.add_product(self.db, "X", self.oil, 12, 0)
        with self.assertRaises(ValueError):
            catalog.add_product(self.db, "X", self.oil, 12, 100, "1.5")

    def test_price_update_and_listing(self):
        p = catalog.add_product(self.db, "Oudh 6ml", self.oil, 6, 700)
        catalog.set_price(self.db, p, "750.50")
        self.assertEqual(catalog.list_products(self.db)[0]["price"], "750.50")
        self.assertEqual(len(catalog.list_bottles(self.db)), 5)


if __name__ == "__main__":
    unittest.main()
