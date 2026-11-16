import unittest
from decimal import Decimal as D
from tests.helpers import fresh_db, seed
from app.services import catalog


class TestCatalogExt(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.s = seed(self.db)

    def test_update_oil(self):
        catalog.update_oil(self.db, self.s["oil"], name="Oudh Royal", density_g_per_ml="0.95")
        o = self.db.one("SELECT * FROM oils")
        self.assertEqual((o["name"], o["density_g_per_ml"]), ("Oudh Royal", "0.95"))
        with self.assertRaises(ValueError):
            catalog.update_oil(self.db, self.s["oil"], density_g_per_ml=0)
        with self.assertRaises(ValueError):
            catalog.update_oil(self.db, 999, name="x")
        catalog.update_oil(self.db, self.s["oil"], active=False)
        self.assertEqual(catalog.list_oils(self.db), [])

    def test_update_product_and_barcode_unique(self):
        catalog.update_product(self.db, self.s["p12"], name="Oudh Gold 12ml", price="1400", barcode=" 8901234567890 ")
        p = self.db.one("SELECT * FROM products WHERE id=?", (self.s["p12"],))
        self.assertEqual((p["name"], p["price"], p["barcode"]), ("Oudh Gold 12ml", "1400", "8901234567890"))
        with self.assertRaises(Exception):                       # same barcode on another product
            catalog.update_product(self.db, self.s["p6"], barcode="8901234567890")
        catalog.update_product(self.db, self.s["p12"], barcode="")          # clearing makes it NULL
        catalog.update_product(self.db, self.s["p6"], barcode="")           # many NULLs are fine
        with self.assertRaises(ValueError):
            catalog.update_product(self.db, self.s["p12"], price=0)

    def test_search_by_name_and_barcode(self):
        catalog.update_product(self.db, self.s["p6"], barcode="111")
        self.assertEqual([p["name"] for p in catalog.search_products(self.db, "12")], ["Oudh 12ml"])
        self.assertEqual([p["name"] for p in catalog.search_products(self.db, "oudh")], ["Oudh 12ml", "Oudh 6ml"])
        self.assertEqual([p["name"] for p in catalog.search_products(self.db, "111")], ["Oudh 6ml"])
        self.assertEqual(catalog.search_products(self.db, "zzz"), [])
        catalog.update_product(self.db, self.s["p6"], active=False)
        self.assertEqual(len(catalog.search_products(self.db, "")), 1)
        self.assertEqual(len(catalog.search_products(self.db, "", include_inactive=True)), 2)

    def test_actual_cost_and_margin(self):
        rows = catalog.enrich_costs(self.db, catalog.search_products(self.db, "12"))
        self.assertEqual((rows[0]["oil_grams"], rows[0]["est_cost"], rows[0]["margin"]), ("10.800", "580.00", "720.00"))
        cap = catalog.add_supply(self.db, "cap", "Gold cap")
        from app.services import purchasing
        purchasing.buy_supply(self.db, self.s["sup"], cap, 100, 500, "2026-11-01")           # 5 each
        catalog.set_product_supplies(self.db, self.s["p12"], [{"supply_id": cap, "qty": 2}])
        rows = catalog.enrich_costs(self.db, catalog.search_products(self.db, "12"))
        self.assertEqual((rows[0]["est_cost"], rows[0]["margin"]), ("590.00", "710.00"))

    def test_supplies_and_product_components(self):
        cap = catalog.add_supply(self.db, "cap", "Gold cap")
        spray = catalog.add_supply(self.db, "spray", "Spray pump")
        box = catalog.add_supply(self.db, "packing", "Gift box")
        self.assertEqual([x["kind"] for x in catalog.list_supplies(self.db)], ["cap", "packing", "spray"])
        self.assertEqual(len(catalog.list_supplies(self.db, "cap")), 1)
        with self.assertRaises(ValueError):
            catalog.add_supply(self.db, "ribbon", "x")
        with self.assertRaises(Exception):
            catalog.add_supply(self.db, "cap", "Gold cap")
        catalog.set_product_supplies(self.db, self.s["p12"], [{"supply_id": cap, "qty": 1}, {"supply_id": box, "qty": 1}])
        self.assertEqual([(x["name"], x["qty"]) for x in catalog.get_product_supplies(self.db, self.s["p12"])],
                         [("Gold cap", 1), ("Gift box", 1)])
        catalog.set_product_supplies(self.db, self.s["p12"], [{"supply_id": spray, "qty": 2}])   # replaces
        self.assertEqual([x["name"] for x in catalog.get_product_supplies(self.db, self.s["p12"])], ["Spray pump"])
        for bad in ([{"supply_id": cap, "qty": 0}], [{"supply_id": cap, "qty": "1.5"}], [{"supply_id": 999, "qty": 1}]):
            with self.assertRaises(ValueError):
                catalog.set_product_supplies(self.db, self.s["p12"], bad)
        self.assertEqual(len(catalog.get_product_supplies(self.db, self.s["p12"])), 1)           # unchanged after errors
        catalog.update_supply(self.db, cap, name="Gold cap XL")
        catalog.update_supply(self.db, box, active=False)
        self.assertEqual(len(catalog.list_supplies(self.db)), 2)


if __name__ == "__main__":
    unittest.main()
