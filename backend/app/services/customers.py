from decimal import Decimal

from app.core.costing import money


def add_customer(db, name, phone=None, address=None, notes=None):
    if not name.strip():
        raise ValueError("name required")
    with db.tx():
        return db.insert("customers", name=name.strip(), phone=(phone or "").strip(), address=address, notes=notes)


def update_customer(db, customer_id, name=None, phone=None, address=None, notes=None, active=None):
    c = db.one("SELECT * FROM customers WHERE id=?", (customer_id,))
    if not c:
        raise ValueError("unknown customer")
    name = c["name"] if name is None else name.strip()
    if not name:
        raise ValueError("name required")
    with db.tx():
        db.execute("UPDATE customers SET name=?, phone=?, address=?, notes=?, active=? WHERE id=?",
                   (name, c["phone"] if phone is None else phone.strip(), c["address"] if address is None else address,
                    c["notes"] if notes is None else notes, c["active"] if active is None else (1 if active else 0), customer_id))


def list_customers(db, q=""):
    q = (q or "").strip().lower()
    rows = db.query("SELECT * FROM customers WHERE active=1 ORDER BY name")
    if q:
        rows = [r for r in rows if q in r["name"].lower() or q in (r["phone"] or "")]
    sums = {}
    for s in db.query("SELECT customer_id, total FROM sales WHERE voided=0 AND customer_id IS NOT NULL"):
        a = sums.setdefault(s["customer_id"], [0, Decimal("0")])
        a[0] += 1
        a[1] += Decimal(s["total"])
    for r in rows:
        n, t = sums.get(r["id"], [0, Decimal("0")])
        r["sales_count"], r["total_spent"] = n, str(money(t))
    return rows


def customer_history(db, customer_id):
    if not db.one("SELECT id FROM customers WHERE id=?", (customer_id,)):
        raise ValueError("unknown customer")
    return db.query("SELECT id, invoice_no, sold_on, total, payment_method, voided FROM sales "
                    "WHERE customer_id=? ORDER BY id DESC", (customer_id,))
