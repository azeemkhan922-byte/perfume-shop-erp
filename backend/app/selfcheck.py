"""End-to-end self-check of the business logic on ANY database (SQLite or PostgreSQL).

    python -m app.selfcheck                       checks a throw-away SQLite database
    set DATABASE_URL=postgresql://...  &  python -m app.selfcheck
        checks PostgreSQL inside a TEMPORARY SCHEMA (azeem_check_xxxx) that is dropped afterwards.
        It never reads or changes your real tables.
"""
import json, sys, uuid
from decimal import Decimal as D

from app import config
from app.db import connect
from app.schema import create_schema
from app.services import (auth, backup, batches, catalog, customers, expenses, inventory, purchasing, reports,
                          sales, settings)
from app.services.pdf_invoice import build_invoice_pdf


def run(db):
    """Runs the purchase -> production -> sale -> report -> backup -> restore story. Returns the list of passed checks."""
    done = []

    def check(cond, name):
        if not cond:
            raise AssertionError("FAILED: " + name)
        done.append(name)

    create_schema(db)
    auth.create_owner(db, "azeem", "a-strong-password")
    settings.set_many(db, {"tax_rate": "5", "upi_id": "azeem@upi"})
    oil = catalog.add_oil(db, "Oudh", "0.90")
    sup = purchasing.add_supplier(db, "Haji & Sons", "0300")
    cap = catalog.add_supply(db, "cap", "Gold cap")
    b12 = next(b["id"] for b in catalog.list_bottles(db) if b["size_ml"] == 12)
    purchasing.record_purchase_invoice(db, sup, "H-101", "2026-11-01", [
        {"kind": "oil", "item_id": oil, "qty": 1, "unit": "kg", "total_price": 50000},
        {"kind": "bottle", "item_id": b12, "qty": 30, "total_price": 1200},
        {"kind": "supply", "item_id": cap, "qty": 100, "total_price": 500}], transport_charge=1000, paid_amount=10000, pay_method="upi")
    check(inventory.get_stock(db, "oil", oil) == D("1000"), "1 kg purchase = 1000 g")
    check(db.one("SELECT avg_cost_per_g a FROM oils")["a"] == "50.9671", "transport is part of the oil cost per gram")
    sm = purchasing.supplier_summary(db)[0]
    check((sm["total_purchased"], sm["total_paid"], sm["balance_due"]) == ("52700.00", "10000.00", "42700.00"), "supplier balance")

    pid = catalog.add_product(db, "Oudh 12ml", oil, 12, 1300, barcode="8901234500012")
    catalog.set_product_supplies(db, pid, [{"supply_id": cap, "qty": 1}])
    batches.make_batch(db, pid, 10, wastage_g=2, made_on="2026-11-05")
    check(inventory.get_stock(db, "oil", oil) == D("890"), "batch used 10 x 10.8 g + 2 g wastage")
    check(catalog.search_products(db, "8901234500012")[0]["stock_qty"] == "10", "barcode finds product with 10 ready bottles")

    cust = customers.add_customer(db, "Ali Khan", "0300555")
    sid = sales.sell(db, [{"product_id": pid, "qty": 12}], customer_id=cust, payment_method="upi", sold_on="2026-11-07")
    s = sales.get_sale(db, sid)
    check((s["subtotal"], s["tax_amount"], s["total"]) == ("15600.00", "780.00", "16380.00"), "sale totals with 5% tax")
    check(inventory.get_stock(db, "oil", oil) == D("868.4"), "sale deducted 2 raw bottles x 10.8 g (10 came from finished stock)")
    check(inventory.get_stock(db, "bottle", b12) == D("18") and inventory.get_stock(db, "supply", cap) == D("88"), "bottles and caps deducted")
    d = reports.daily_report(db, "2026-11-07")
    check((d["revenue"], d["tax_collected"]) == ("15600.00", "780.00"), "revenue excludes tax")
    pdf = build_invoice_pdf(s, "AZEEM FRAGRANCES", settings.get_all(db))
    check(pdf.startswith(b"%PDF") and b"INV-" in pdf, "PDF invoice")
    expenses.add_expense(db, "2026-11-07", "Rent", 500)
    check(reports.monthly_report(db, "2026-11")["expenses"] == "500.00", "expense in monthly report")

    raw = backup.export_json(db)
    sales.void_sale(db, sid, "test")
    check(inventory.get_stock(db, "oil", oil) == D("890"), "cancelled sale restored stock")
    counts = backup.restore_json(db, raw)
    check(counts["sales"] == 1 and sales.get_sale(db, sid)["voided"] == 0, "restore brought the sale back")
    check(inventory.get_stock(db, "oil", oil) == D("868.4"), "restore brought the stock back")
    check(purchasing.add_supplier(db, "After restore") > sup, "new ids continue after the restored ones")
    check(auth.login(db, "azeem", "a-strong-password", "k" * 40, 1), "owner login works after restore")
    try:
        sales.sell(db, [{"product_id": pid, "qty": 500}], sold_on="2026-11-07")
        check(False, "overselling must be refused")
    except ValueError:
        done.append("overselling is refused and changes nothing")
    check(inventory.get_stock(db, "oil", oil) == D("868.4"), "failed sale changed nothing")
    return done


def run_on_url(url):
    """SQLite: throw-away file. PostgreSQL: temporary schema, dropped at the end."""
    if url.startswith("sqlite"):
        import os, tempfile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = connect("sqlite:///" + os.path.join(tmp, "check.db").replace("\\", "/"))
            try:
                return run(db)
            finally:
                db.conn.close()
    db = connect(url)
    schema = "azeem_check_" + uuid.uuid4().hex[:8]
    try:
        db.execute(f"CREATE SCHEMA {schema}"); db.conn.commit()
        db.execute(f"SET search_path TO {schema}"); db.conn.commit()
        return run(db)
    finally:
        try:
            db.conn.rollback()
            db.execute("SET search_path TO public"); db.conn.commit()
            db.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE"); db.conn.commit()
        finally:
            db.conn.close()


def main():
    url = config.DATABASE_URL
    kind = "SQLite (throw-away file)" if url.startswith("sqlite") else "PostgreSQL (temporary schema)"
    print("Self-check on", kind)
    try:
        for name in run_on_url(url):
            print("  ok  ", name)
    except Exception as e:
        print("  FAIL", type(e).__name__, e)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
