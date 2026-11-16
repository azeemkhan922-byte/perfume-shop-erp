"""End-to-end tests of every HTTP endpoint using a temporary SQLite file.
They need FastAPI + httpx (pip install -r requirements-dev.txt) and are SKIPPED when those are missing."""
import os, tempfile, unittest

try:
    from fastapi.testclient import TestClient
    HAVE = True
except Exception:  # pragma: no cover
    HAVE = False

SECRET = "t" * 40


@unittest.skipUnless(HAVE, "FastAPI/httpx not installed - run: pip install -r requirements-dev.txt")
class TestApi(unittest.TestCase):
    def setUp(self):
        from app import config
        from app.db import connect
        from app.services import auth
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        config.DATABASE_URL = "sqlite:///" + os.path.join(self.tmp.name, "t.db")
        config.SECRET_KEY = SECRET
        from app.main import app
        self.cm = TestClient(app)
        self.c = self.cm.__enter__()                      # runs startup (creates tables)
        db = connect(config.DATABASE_URL)
        auth.create_owner(db, "azeem", "a-strong-password")
        db.conn.close()

    def tearDown(self):
        self.cm.__exit__(None, None, None)
        self.tmp.cleanup()

    def login(self):
        r = self.c.post("/api/login", json={"username": "azeem", "password": "a-strong-password"})
        self.assertEqual(r.status_code, 200)
        return {"Authorization": "Bearer " + r.json()["token"]}

    def test_health_is_public(self):
        self.assertEqual(self.c.get("/api/health").json(), {"status": "UP"})

    def test_login_wrong_password_and_protection(self):
        self.assertEqual(self.c.post("/api/login", json={"username": "azeem", "password": "wrong-password-1"}).status_code, 401)
        for path in ("/api/oils", "/api/products", "/api/suppliers", "/api/purchases", "/api/sales",
                     "/api/expenses", "/api/reports/dashboard", "/api/reports/daily?day=2026-11-07"):
            self.assertEqual(self.c.get(path).status_code, 401, path)
        self.assertEqual(self.c.get("/api/oils", headers={"Authorization": "Bearer junk"}).status_code, 401)

    def test_cors_allows_only_configured_origins(self):
        ok = self.c.options("/api/login", headers={"Origin": "http://localhost:5173",
                            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"})
        self.assertEqual(ok.headers.get("access-control-allow-origin"), "http://localhost:5173")
        bad = self.c.options("/api/login", headers={"Origin": "http://evil.example",
                             "Access-Control-Request-Method": "POST"})
        self.assertNotIn("access-control-allow-origin", bad.headers)

    def test_full_shop_flow(self):
        h = self.login()
        oil = self.c.post("/api/oils", json={"name": "Oudh", "density_g_per_ml": "0.90"}, headers=h).json()["id"]
        self.assertEqual(self.c.post("/api/oils", json={"name": "Oudh", "density_g_per_ml": "0.9"}, headers=h).status_code, 409)
        self.assertEqual(self.c.post("/api/oils", json={"name": "Bad", "density_g_per_ml": "0"}, headers=h).status_code, 400)
        sup = self.c.post("/api/suppliers", json={"name": "Haji", "phone": "0300"}, headers=h).json()["id"]
        self.assertEqual(len(self.c.get("/api/suppliers", headers=h).json()), 1)
        self.assertEqual(len(self.c.get("/api/bottles", headers=h).json()), 5)

        r = self.c.post("/api/purchases/oil", headers=h, json={"supplier_id": sup, "oil_id": oil, "qty": "1",
                        "unit": "kg", "total_price": "50000", "purchased_on": "2026-11-01"})
        self.assertEqual(r.status_code, 200, r.text)
        valid_purchase = {"supplier_id": sup, "oil_id": oil, "qty": "1", "unit": "kg",
                          "total_price": "1000", "purchased_on": "2026-11-01"}
        # Authentication: a perfectly VALID request without the token must be refused (401) and change nothing.
        self.assertEqual(self.c.post("/api/purchases/oil", json=valid_purchase).status_code, 401)
        self.assertEqual(self.c.get("/api/oils", headers=h).json()[0]["stock_g"], "1000.000")
        # Validation: with the token, an INVALID unit is rejected with 400.
        self.assertEqual(self.c.post("/api/purchases/oil", headers=h, json={**valid_purchase, "unit": "stone"}).status_code, 400)
        self.assertEqual(self.c.get("/api/oils", headers=h).json()[0]["stock_g"], "1000.000")
        r = self.c.post("/api/purchases/bottles", headers=h, json={"supplier_id": sup, "size_ml": 12, "qty": 10,
                        "total_price": "400", "purchased_on": "2026-11-01"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(self.c.get("/api/purchases", headers=h).json()), 2)
        self.assertEqual(self.c.get("/api/oils", headers=h).json()[0]["stock_g"], "1000.000")

        p = self.c.post("/api/products", headers=h, json={"name": "Oudh 12ml", "oil_id": oil, "bottle_ml": 12,
                        "price": "1300"}).json()["id"]
        valid_product = {"name": "Rose 6ml", "oil_id": oil, "bottle_ml": 6, "price": "700"}
        self.assertEqual(self.c.post("/api/products", json=valid_product).status_code, 401)      # valid body, no token
        self.assertEqual(self.c.post("/api/products", headers=h, json={**valid_product, "bottle_ml": 7}).status_code, 400)  # token, bad size
        self.assertEqual(len(self.c.get("/api/products", headers=h).json()), 1)

        s = self.c.post("/api/sales", headers=h, json={"items": [{"product_id": p, "qty": 2}], "customer_name": "Ali",
                        "payment_method": "cash", "discount": "100", "sold_on": "2026-11-07"})
        self.assertEqual(s.status_code, 200, s.text)
        sid, inv = s.json()["id"], s.json()["invoice_no"]
        self.assertEqual(inv, f"INV-{sid:06d}")
        self.assertEqual(self.c.get("/api/oils", headers=h).json()[0]["stock_g"], "978.400")   # 1000 - 2*10.8
        sale = self.c.get(f"/api/sales/{sid}", headers=h).json()
        self.assertEqual((sale["total"], len(sale["items"])), ("2500.00", 1))
        self.assertEqual(self.c.get("/api/sales/9999", headers=h).status_code, 404)
        self.assertEqual(len(self.c.get("/api/sales?day=2026-11-07", headers=h).json()), 1)

        too_many = self.c.post("/api/sales", headers=h, json={"items": [{"product_id": p, "qty": 50}], "sold_on": "2026-11-07"})
        self.assertEqual(too_many.status_code, 400)
        self.assertEqual(self.c.get("/api/oils", headers=h).json()[0]["stock_g"], "978.400")

        pdf = self.c.get(f"/api/sales/{sid}/invoice.pdf", headers=h)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers["content-type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF-1.4") and inv.encode() in pdf.content)
        self.assertEqual(self.c.get(f"/api/sales/{sid}/invoice.pdf").status_code, 401)

        e = self.c.post("/api/expenses", headers=h, json={"spent_on": "2026-11-07", "category": "Rent", "amount": "500"})
        self.assertEqual(e.status_code, 200, e.text)
        self.assertEqual(self.c.post("/api/expenses", headers=h, json={"spent_on": "bad", "category": "Rent", "amount": "5"}).status_code, 400)
        self.assertEqual(len(self.c.get("/api/expenses?month=2026-11", headers=h).json()), 1)

        d = self.c.get("/api/reports/daily?day=2026-11-07", headers=h).json()
        self.assertEqual((d["revenue"], d["cost_of_goods"], d["expenses"], d["net_profit"]),
                         ("2500.00", "1160.00", "500.00", "840.00"))
        m = self.c.get("/api/reports/monthly?month=2026-11", headers=h).json()
        self.assertEqual(m["net_profit"], "840.00")
        self.assertEqual(self.c.get("/api/reports/daily?day=bad", headers=h).status_code, 400)
        self.assertEqual(self.c.get("/api/reports/dashboard", headers=h).status_code, 200)

        self.assertEqual(self.c.post(f"/api/sales/{sid}/void", headers=h, json={"reason": "returned"}).status_code, 200)
        self.assertEqual(self.c.post(f"/api/sales/{sid}/void", headers=h, json={}).status_code, 400)
        self.assertEqual(self.c.get("/api/oils", headers=h).json()[0]["stock_g"], "1000.000")
        self.assertEqual(self.c.get("/api/reports/daily?day=2026-11-07", headers=h).json()["revenue"], "0.00")

        self.assertEqual(self.c.post("/api/stocktake", headers=h, json={"item_type": "oil", "item_id": oil, "counted": "990"}).json(),
                         {"balance": "990.000"})
        self.assertEqual(self.c.post("/api/stocktake", headers=h, json={"item_type": "gold", "item_id": 1, "counted": "1"}).status_code, 400)
        led = self.c.get(f"/api/stock/oil/{oil}/ledger", headers=h).json()
        self.assertEqual([x["kind"] for x in led], ["purchase", "sale", "sale_void", "adjustment"])

        self.assertEqual(self.c.delete("/api/expenses/1", headers=h).status_code, 200)
        self.assertEqual(self.c.get("/api/expenses", headers=h).json(), [])


if __name__ == "__main__":
    unittest.main()
