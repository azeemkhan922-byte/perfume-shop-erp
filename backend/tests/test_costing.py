import unittest
from decimal import Decimal as D
from app.core.costing import weighted_avg_cost, batch_cost, profit


class TestCosting(unittest.TestCase):
    def test_first_purchase(self):
        # 1000 g bought for Rs 50,000 -> Rs 50/g
        self.assertEqual(weighted_avg_cost(0, 0, 1000, 50000), D("50.0000"))

    def test_second_purchase_averages(self):
        # 1000 g @50 + 500 g for Rs 40,000 (80/g) -> 90000/1500 = 60
        self.assertEqual(weighted_avg_cost(1000, 50, 500, 40000), D("60.0000"))

    def test_batch_cost(self):
        # 10 bottles of 12ml @0.9 = 108 g oil @50 = 5400 + bottles 10*30 + 100 other
        total, each = batch_cost(108, 50, 30, 10, 100)
        self.assertEqual(total, D("5800.00"))
        self.assertEqual(each, D("580.00"))

    def test_profit(self):
        self.assertEqual(profit(1000, "580.50"), D("419.50"))

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            weighted_avg_cost(0, 0, 0, 100)
        with self.assertRaises(ValueError):
            batch_cost(10, 5, 1, 0)


if __name__ == "__main__":
    unittest.main()
