"""Tests the real HTTP API layer (everything except the thin FastAPI wrapper) - these run without FastAPI."""
import json, threading, unittest, urllib.request, urllib.error
from decimal import Decimal as D
from tests.api_helper import Api, PASSWORD


class TestApiBasics(unittest.TestCase):
    def setUp(self):
        self.api = Api(); self.api.login()

    def tearDown(self):
        self.api.close()

    def test_health_is_public_and_everything_else_needs_login(self):
        self.assertEqual(self.api.call("GET", "/api/health", token=None)[:2], (200, {"status": "UP"}))
        for m, path in (("GET", "/api/oils"), ("GET", "/api/products"), ("GET", "/api/suppliers"), ("GET", "/api/purchases"),
                        ("GET", "/api/sales"), ("GET", "/api/expenses"), ("GET", "/api/customers"), ("GET", "/api/batches"),
                        ("GET", "/api/settings"), ("GET", "/api/supplies"), ("GET", "/api/bottles"), ("GET", "/api/backup"),
                        ("GET", "/api/reports/dashboard"), ("GET", "/api/reports/stock"), ("GET", "/api/reports/daily?day=2026-11-07"),
                        ("GET", "/api/reports/monthly?month=2026-11"), ("GET", "/api/me"), ("GET", "/api/sales/1/invoice.pdf"),
                        ("POST", "/api/oils"), ("POST", "/api/sales"), ("POST", "/api/restore"), ("PUT", "/api/settings"),
                        ("DELETE", "/api/expenses/1"), ("POST", "/api/change-password")):
            self.assertEqual(self.api.call(m, path, {}, token=None)[0], 401, path)
            self.assertEqual(self.api.call(m, path, {}, token="garbage")[0], 401, path)

    def test_login(self):
        c = lambda b: self.api.call("POST", "/api/login", b, token=None)[0]
        self.assertEqual(c({"username": "azeem", "password": "wrong-password-1"}), 401)
        self.assertEqual(c({"username": "azeem"}), 400)
        self.assertEqual(c({}), 400)
        self.assertEqual(self.api.call("GET", "/api/me")[1]["ok"], True)

    def test_error_mapping(self):
        self.assertEqual(self.api.call("GET", "/api/nope")[0], 404)
        self.assertEqual(self.api.call("DELETE", "/api/oils")[0], 405)
        self.assertEqual(self.api.call("POST", "/api/oils", raw_body=b"{{{")[0], 400)
        self.assertEqual(self.api.call("POST", "/api/oils", raw_body=b"[1,2]")[0], 400)
        self.assertEqual(self.api.call("POST", "/api/oils", {"name": "X"})[0], 400)                         # missing field
        self.assertEqual(self.api.call("POST", "/api/oils", {"name": "X", "density_g_per_ml": "abc"})[0], 400)  # bad number
        self.assertEqual(self.api.call("POST", "/api/oils", {"name": "X", "density_g_per_ml": 0})[0], 400)
        self.assertEqual(self.api.call("POST", "/api/oils", {"name": "Oudh", "density_g_per_ml": "0.9"})[0], 200)
        self.assertEqual(self.api.call("POST", "/api/oils", {"name": "Oudh", "density_g_per_ml": "0.9"})[0], 409)
        self.assertEqual(self.api.call("GET", "/api/sales/999")[0], 404)
        self.assertEqual(self.api.call("GET", "/api/reports/daily")[0], 400)
        self.assertEqual(self.api.call("GET", "/api/reports/daily?day=bad")[0], 400)

    def test_settings(self):
        self.assertEqual(self.api.ok("GET", "/api/settings")["shop_name"], "AZEEM FRAGRANCES")
        out = self.api.ok("PUT", "/api/settings", {"tax_rate": "5", "shop_phone": "0300", "upi_id": "azeem@upi"})
        self.assertEqual((out["tax_rate"], out["upi_id"]), ("5", "azeem@upi"))
        self.assertEqual(self.api.call("PUT", "/api/settings", {"tax_rate": "500"})[0], 400)
        self.assertEqual(self.api.call("PUT", "/api/settings", {"hacker": "1"})[0], 400)

    def test_change_password(self):
        self.assertEqual(self.api.call("POST", "/api/change-password", {"old_password": "wrong-old-pass", "new_password": "brand-new-password"})[0], 403)
        self.assertEqual(self.api.call("POST", "/api/change-password", {"old_password": PASSWORD, "new_password": "short"})[0], 400)
        self.api.ok("POST", "/api/change-password", {"old_password": PASSWORD, "new_password": "brand-new-password"})
        self.assertEqual(self.api.call("POST", "/api/login", {"username": "azeem", "password": PASSWORD}, token=None)[0], 401)
        self.assertEqual(self.api.call("POST", "/api/login", {"username": "azeem", "password": "brand-new-password"}, token=None)[0], 200)


class TestPurchaseToSaleWorkflow(unittest.TestCase):
    """The whole shop story through the HTTP API: set up, buy, produce, sell, bill, report, back up, restore."""

    def setUp(self):
        self.api = Api(); self.api.login()

    def tearDown(self):
        self.api.close()

    def test_complete_workflow(self):
        a = self.api
        a.ok("PUT", "/api/settings", {"tax_rate": "5", "shop_phone": "0300 1234567", "upi_id": "azeem@upi"})
        oil = a.ok("POST", "/api/oils", {"name": "Oudh", "density_g_per_ml": "0.90"})["id"]
        sup = a.ok("POST", "/api/suppliers", {"name": "Haji & Sons", "phone": "0300"})["id"]
        cap = a.ok("POST", "/api/supplies", {"kind": "cap", "name": "Gold cap"})["id"]
        b12 = next(b["id"] for b in a.ok("GET", "/api/bottles") if b["size_ml"] == 12)

        # purchase invoice with transport, part-paid
        a.ok("POST", "/api/purchases/invoice", {"supplier_id": sup, "invoice_no": "H-101", "purchased_on": "2026-11-01",
             "transport_charge": 1000, "paid_amount": 10000, "pay_method": "upi", "lines": [
                 {"kind": "oil", "item_id": oil, "qty": 1, "unit": "kg", "total_price": 50000},
                 {"kind": "bottle", "item_id": b12, "qty": 30, "total_price": 1200},
                 {"kind": "supply", "item_id": cap, "qty": 100, "total_price": 500}]})
        purchases = a.ok("GET", "/api/purchases")
        self.assertEqual(sum(D(p["transport_charge"]) for p in purchases), D("1000"))
        o = a.ok("GET", "/api/oils")[0]
        self.assertEqual(o["stock_g"], "1000.000")                         # 1 kg = 1000 g
        self.assertEqual(o["avg_cost_per_g"], "50.9671")                   # (50000 + 967.12 transport share) / 1000 g
        sup_row = a.ok("GET", "/api/suppliers")[0]
        self.assertEqual(sup_row["total_paid"], "10000.00")
        self.assertEqual(D(sup_row["total_purchased"]), D("52700.00"))     # 51,700 goods + 1,000 transport
        self.assertEqual(D(sup_row["balance_due"]), D("42700.00"))

        # product with barcode and a cap per unit; produce a batch with wastage
        pid = a.ok("POST", "/api/products", {"name": "Oudh Royal 12ml", "oil_id": oil, "bottle_ml": 12, "price": "1300", "barcode": "8901234500012"})["id"]
        a.ok("PUT", f"/api/products/{pid}/supplies", {"items": [{"supply_id": cap, "qty": 1}]})
        a.ok("POST", "/api/batches", {"product_id": pid, "units": 10, "wastage_g": 2, "other_cost": 0, "made_on": "2026-11-05"})
        self.assertEqual(a.ok("GET", "/api/oils")[0]["stock_g"], "890.000")          # 10 x 10.8 g + 2 g wastage = 110 g used
        batch = a.ok("GET", "/api/batches")[0]
        oil_avg, b_avg, c_avg = D("50.9671"), D(next(b for b in a.ok("GET", "/api/bottles") if b["id"] == b12)["avg_cost_each"]), D(a.ok("GET", "/api/supplies")[0]["avg_cost_each"])
        self.assertEqual(D(batch["unit_cost"]), ((D("110") * oil_avg + 10 * b_avg + 10 * c_avg) / 10).quantize(D("0.0001")))
        self.assertEqual(batch["wastage_g"], "2.000")

        # POS: find by barcode, sell 12 (10 finished + 2 filled from raw), with a customer
        cust = a.ok("POST", "/api/customers", {"name": "Ali Khan", "phone": "0300555"})["id"]
        found = a.ok("GET", "/api/products?q=8901234500012")
        self.assertEqual([p["name"] for p in found], ["Oudh Royal 12ml"])
        self.assertEqual(found[0]["stock_qty"], "10")
        sale = a.ok("POST", "/api/sales", {"items": [{"product_id": pid, "qty": 12}], "customer_id": cust, "payment_method": "upi", "discount": 0, "sold_on": "2026-11-07"})
        sid = sale["id"]
        s = a.ok("GET", f"/api/sales/{sid}")
        self.assertEqual((s["subtotal"], s["tax_amount"], s["total"], s["customer_name"]), ("15600.00", "780.00", "16380.00", "Ali Khan"))
        self.assertEqual(s["items"][0]["finished_qty"], 10)
        self.assertEqual(a.ok("GET", "/api/oils")[0]["stock_g"], "868.400")           # 890 - 2 x 10.8
        self.assertEqual(next(b for b in a.ok("GET", "/api/bottles") if b["id"] == b12)["stock_qty"], "18")
        self.assertEqual(a.ok("GET", "/api/supplies")[0]["stock_qty"], "88")

        # invoice PDF
        st, pdf, hd = a.call("GET", f"/api/sales/{sid}/invoice.pdf")
        self.assertEqual(st, 200); self.assertEqual(hd["Content-Type"], "application/pdf")
        for needle in (sale["invoice_no"].encode(), b"AZEEM FRAGRANCES", b"Ali Khan", b"GST", b"Rs. 16380.00", b"azeem@upi"):
            self.assertIn(needle, pdf)

        # reports: revenue excludes tax; profit uses frozen cost
        a.ok("POST", "/api/expenses", {"spent_on": "2026-11-07", "category": "Rent", "amount": "500"})
        day = a.ok("GET", "/api/reports/daily?day=2026-11-07")
        self.assertEqual((day["revenue"], day["tax_collected"]), ("15600.00", "780.00"))
        raw_cost = 2 * (D("10.8") * oil_avg + b_avg + c_avg)
        expected_cogs = (10 * D(batch["unit_cost"]) + raw_cost).quantize(D("0.01"))
        self.assertEqual(D(day["cost_of_goods"]), expected_cogs)
        self.assertEqual(D(day["net_profit"]), D("15600") - expected_cogs - D("500"))
        month = a.ok("GET", "/api/reports/monthly?month=2026-11")
        self.assertEqual(month["wastage_g"], "2.000")
        stock = a.ok("GET", "/api/reports/stock")
        self.assertTrue(D(stock["total_value"]) > 0)
        dash = a.ok("GET", "/api/reports/dashboard")
        self.assertTrue({"inventory_value", "low_stock", "best_sellers"} <= set(dash))
        self.assertEqual(a.ok("GET", f"/api/customers/{cust}/history")[0]["id"], sid)
        self.assertEqual(a.ok("GET", "/api/customers")[0]["total_spent"], "16380.00")

        # backup, wreck the data, restore
        st, backup_bytes, hd = a.call("GET", "/api/backup")
        self.assertEqual(st, 200); self.assertIn("attachment", hd["Content-Disposition"])
        backup = backup_bytes            # already parsed JSON (the file is JSON)
        a.ok("POST", f"/api/sales/{sid}/void", {"reason": "test"})
        a.ok("POST", "/api/expenses", {"spent_on": "2026-11-09", "category": "Tea", "amount": "5"})
        self.assertEqual(a.call("POST", "/api/restore", {"password": "wrong-password-1", "backup": backup})[0], 403)
        self.assertEqual(a.call("POST", "/api/restore", {"password": PASSWORD, "backup": {"app": "other"}})[0], 400)
        self.assertEqual(a.ok("GET", f"/api/sales/{sid}")["voided"], 1)               # failed restores changed nothing
        out = a.ok("POST", "/api/restore", {"password": PASSWORD, "backup": backup})
        self.assertEqual(out["restored"]["sales"], 1)
        self.assertEqual(a.ok("GET", f"/api/sales/{sid}")["voided"], 0)
        self.assertEqual(len(a.ok("GET", "/api/expenses")), 1)
        self.assertEqual(a.ok("GET", "/api/oils")[0]["stock_g"], "868.400")

        # void puts everything back
        a.ok("POST", f"/api/sales/{sid}/void", {"reason": "customer returned"})
        self.assertEqual(a.ok("GET", "/api/oils")[0]["stock_g"], "890.000")
        self.assertEqual(a.ok("GET", "/api/supplies")[0]["stock_qty"], "90")
        self.assertEqual(a.ok("GET", "/api/products")[0]["stock_qty"], "10")

    def test_stock_shortage_gives_a_readable_400_and_changes_nothing(self):
        a = self.api
        oil = a.ok("POST", "/api/oils", {"name": "Oudh", "density_g_per_ml": "0.9"})["id"]
        pid = a.ok("POST", "/api/products", {"name": "Oudh 12ml", "oil_id": oil, "bottle_ml": 12, "price": 1300})["id"]
        st, out, _ = a.call("POST", "/api/sales", {"items": [{"product_id": pid, "qty": 1}]})
        self.assertEqual(st, 400); self.assertIn("insufficient stock", out["detail"])
        self.assertEqual(a.ok("GET", "/api/sales"), [])

    def test_stocktake_and_ledger_for_every_item_type(self):
        a = self.api
        oil = a.ok("POST", "/api/oils", {"name": "Rose", "density_g_per_ml": "0.85"})["id"]
        cap = a.ok("POST", "/api/supplies", {"kind": "cap", "name": "Cap"})["id"]
        self.assertEqual(a.ok("POST", "/api/stocktake", {"item_type": "oil", "item_id": oil, "counted": "250.5"})["balance"], "250.500")
        self.assertEqual(a.ok("POST", "/api/stocktake", {"item_type": "supply", "item_id": cap, "counted": 40})["balance"], "40")
        self.assertEqual(a.call("POST", "/api/stocktake", {"item_type": "supply", "item_id": cap, "counted": "1.5"})[0], 400)
        self.assertEqual(a.call("POST", "/api/stocktake", {"item_type": "gold", "item_id": 1, "counted": 1})[0], 400)
        self.assertEqual([r["kind"] for r in a.ok("GET", f"/api/stock/oil/{oil}/ledger")], ["adjustment"])
        self.assertEqual(a.call("GET", "/api/stock/gold/1/ledger")[0], 400)

    def test_crud_endpoints_used_by_the_screens(self):
        a = self.api
        oil = a.ok("POST", "/api/oils", {"name": "Rose", "density_g_per_ml": "0.85"})["id"]
        a.ok("PUT", f"/api/oils/{oil}", {"name": "Rose Taifi", "density_g_per_ml": "0.88"})
        self.assertEqual(a.ok("GET", "/api/oils")[0]["name"], "Rose Taifi")
        a.ok("POST", "/api/bottles", {"size_ml": 3})
        self.assertEqual(len(a.ok("GET", "/api/bottles")), 6)
        sup = a.ok("POST", "/api/suppliers", {"name": "S"})["id"]
        a.ok("PUT", f"/api/suppliers/{sup}", {"name": "S2", "phone": "1"})
        a.ok("POST", "/api/supplier-payments", {"supplier_id": sup, "amount": 100, "paid_on": "2026-11-07", "method": "cash"})
        self.assertEqual(len(a.ok("GET", f"/api/supplier-payments?supplier_id={sup}")), 1)
        self.assertEqual(a.call("POST", "/api/supplier-payments", {"supplier_id": sup, "amount": 0, "paid_on": "2026-11-07"})[0], 400)
        pid = a.ok("POST", "/api/products", {"name": "Rose 6ml", "oil_id": oil, "bottle_ml": 6, "price": 500})["id"]
        a.ok("PUT", f"/api/products/{pid}", {"price": "550", "barcode": "123"})
        self.assertEqual(a.ok("GET", "/api/products?q=123")[0]["price"], "550")
        a.ok("PUT", f"/api/products/{pid}", {"active": False})
        self.assertEqual(a.ok("GET", "/api/products"), []); self.assertEqual(len(a.ok("GET", "/api/products?all=1")), 1)
        sp = a.ok("PUT", f"/api/supplies/{a.ok('POST', '/api/supplies', {'kind': 'spray', 'name': 'Pump'})['id']}", {"name": "Pump XL"})
        c = a.ok("POST", "/api/customers", {"name": "Sara"})["id"]
        a.ok("PUT", f"/api/customers/{c}", {"phone": "0321"})
        self.assertEqual(a.ok("GET", "/api/customers?q=0321")[0]["name"], "Sara")
        e = a.ok("POST", "/api/expenses", {"spent_on": "2026-11-07", "category": "Rent", "amount": 10})["id"]
        a.ok("DELETE", f"/api/expenses/{e}")
        self.assertEqual(a.ok("GET", "/api/expenses?month=2026-11"), [])

    def test_sales_list_filters(self):
        a = self.api
        oil = a.ok("POST", "/api/oils", {"name": "Oudh", "density_g_per_ml": "0.9"})["id"]
        sup = a.ok("POST", "/api/suppliers", {"name": "S"})["id"]
        a.ok("POST", "/api/purchases/oil", {"supplier_id": sup, "oil_id": oil, "qty": 1, "unit": "kg", "total_price": 50000, "purchased_on": "2026-11-01"})
        a.ok("POST", "/api/purchases/bottles", {"supplier_id": sup, "size_ml": 12, "qty": 10, "total_price": 400, "purchased_on": "2026-11-01"})
        pid = a.ok("POST", "/api/products", {"name": "Oudh 12ml", "oil_id": oil, "bottle_ml": 12, "price": 1300})["id"]
        a.ok("POST", "/api/sales", {"items": [{"product_id": pid, "qty": 1}], "customer_name": "Walk Ali", "sold_on": "2026-11-07"})
        a.ok("POST", "/api/sales", {"items": [{"product_id": pid, "qty": 1}], "customer_name": "Bilal", "sold_on": "2026-11-08"})
        self.assertEqual(len(a.ok("GET", "/api/sales?day=2026-11-07")), 1)
        self.assertEqual(a.ok("GET", "/api/sales?q=bilal")[0]["customer_name"], "Bilal")
        self.assertEqual(a.ok("GET", "/api/sales?q=INV-000001")[0]["id"], 1)


class TestRealHttpServer(unittest.TestCase):
    """Starts the standard-library server on a real socket and talks to it over HTTP."""

    def test_login_and_protected_call_over_http(self):
        import os; os.environ["QUIET"] = "1"
        from http.server import ThreadingHTTPServer
        from app.devserver import Handler
        api = Api()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            def call(method, path, body=None, token=None):
                req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                             headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
                try:
                    with urllib.request.urlopen(req) as r:
                        return r.status, r.read()
                except urllib.error.HTTPError as e:
                    return e.code, e.read()
            self.assertEqual(call("GET", "/api/health"), (200, b'{"status": "UP"}'))
            self.assertEqual(call("GET", "/api/oils")[0], 401)
            st, body = call("POST", "/api/login", {"username": "azeem", "password": PASSWORD})
            self.assertEqual(st, 200)
            tok = json.loads(body)["token"]
            self.assertEqual(call("POST", "/api/oils", {"name": "Oudh", "density_g_per_ml": "0.9"}, tok)[0], 200)
            self.assertEqual(json.loads(call("GET", "/api/oils", token=tok)[1])[0]["name"], "Oudh")
            self.assertEqual(call("GET", "/")[0] in (200, 404), True)                        # static route does not crash
        finally:
            srv.shutdown(); srv.server_close(); api.close()


if __name__ == "__main__":
    unittest.main()
