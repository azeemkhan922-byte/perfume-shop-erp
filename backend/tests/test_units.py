import unittest
from decimal import Decimal as D
from app.core.units import to_grams, oil_grams_for_bottle, deduct_stock


class TestUnits(unittest.TestCase):
    def test_1kg_is_1000g(self):
        self.assertEqual(to_grams(1, "kg"), D("1000.000"))

    def test_decimal_kg_and_g(self):
        self.assertEqual(to_grams("2.5", "kg"), D("2500.000"))
        self.assertEqual(to_grams(250, "g"), D("250.000"))

    def test_ml_needs_density(self):
        with self.assertRaises(ValueError):
            to_grams(100, "ml")
        self.assertEqual(to_grams(100, "ml", "0.9"), D("90.000"))

    def test_bottle_not_1g_per_ml(self):
        self.assertEqual(oil_grams_for_bottle(6, "0.90"), D("5.400"))
        self.assertEqual(oil_grams_for_bottle(12, "0.90"), D("10.800"))
        self.assertNotEqual(oil_grams_for_bottle(12, "0.90"), D("12"))

    def test_different_density_different_result(self):
        self.assertEqual(oil_grams_for_bottle(12, "0.95"), D("11.400"))

    def test_diluted_bottle(self):
        # 12ml bottle, 25% oil by volume, density 0.9 -> 2.7 g
        self.assertEqual(oil_grams_for_bottle(12, "0.9", "0.25"), D("2.700"))

    def test_full_flow_1kg_then_sell_bottles(self):
        stock = to_grams(1, "kg")
        stock = deduct_stock(stock, oil_grams_for_bottle(6, "0.9"))
        stock = deduct_stock(stock, oil_grams_for_bottle(12, "0.9") * 2)
        self.assertEqual(stock, D("1000") - D("5.4") - D("21.6"))

    def test_no_negative_stock(self):
        with self.assertRaises(ValueError):
            deduct_stock(5, 5.4)

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            to_grams(-1, "kg")
        with self.assertRaises(ValueError):
            to_grams(1, "stone")
        with self.assertRaises(ValueError):
            oil_grams_for_bottle(12, 0)


if __name__ == "__main__":
    unittest.main()
