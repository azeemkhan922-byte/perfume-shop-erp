"""Suppliers and purchases. A purchase raises stock and updates average cost, atomically."""
from decimal import Decimal

from app.core.costing import money, weighted_avg_cost
from app.core.units import to_grams
from app.db import now
from app.services import inventory


def add_supplier(db, name, phone=None, notes=None):
    if not name.strip():
        raise ValueError("name required")
    with db.tx():
        return db.insert("suppliers", name=name.strip(), phone=phone, notes=notes)


def list_suppliers(db):
    return db.query("SELECT * FROM suppliers ORDER BY name")


def _landed(total_price, transport_charge) -> Decimal:
    t = Decimal(str(transport_charge))
    if t < 0:
        raise ValueError("transport charge cannot be negative")
    return Decimal(str(total_price)) + t


def _check(db, supplier_id, price):
    if not db.one("SELECT id FROM suppliers WHERE id=?", (supplier_id,)):
        raise ValueError("unknown supplier")
    if Decimal(str(price)) < 0:
        raise ValueError("price cannot be negative")


def buy_oil(db, supplier_id, oil_id, qty, unit, total_price, purchased_on, transport_charge=0, invoice_no=None):
    _check(db, supplier_id, total_price)
    oil = db.one("SELECT * FROM oils WHERE id=?", (oil_id,))
    if not oil:
        raise ValueError("unknown oil")
    grams = to_grams(qty, unit, oil["density_g_per_ml"])  # 1 kg -> 1000 g; ml uses this oil's density
    if grams <= 0:
        raise ValueError("quantity must be positive")
    landed = _landed(total_price, transport_charge)
    with db.tx():
        new_avg = weighted_avg_cost(oil["stock_g"], oil["avg_cost_per_g"], grams, landed)
        pid = db.insert("purchases", supplier_id=supplier_id, kind="oil", item_id=oil_id, qty=str(qty),
                        unit=unit.lower(), base_qty=str(grams), total_price=str(Decimal(str(total_price))),
                        purchased_on=purchased_on, created_at=now(), invoice_no=invoice_no,
                        transport_charge=str(Decimal(str(transport_charge))), landed_total=str(landed))
        inventory.change_stock(db, "oil", oil_id, grams, "purchase", "purchase", pid)
        db.execute("UPDATE oils SET avg_cost_per_g=? WHERE id=?", (str(new_avg), oil_id))
    return pid


def buy_bottles(db, supplier_id, size_ml, qty, total_price, purchased_on, transport_charge=0, invoice_no=None):
    _check(db, supplier_id, total_price)
    b = db.one("SELECT * FROM bottles WHERE size_ml=?", (int(size_ml),))
    if not b:
        raise ValueError("unknown bottle size")
    n = Decimal(str(qty))
    if n <= 0 or n != n.to_integral_value():
        raise ValueError("bottle quantity must be a positive whole number")
    landed = _landed(total_price, transport_charge)
    with db.tx():
        new_avg = weighted_avg_cost(b["stock_qty"], b["avg_cost_each"], n, landed)
        pid = db.insert("purchases", supplier_id=supplier_id, kind="bottle", item_id=b["id"], qty=str(n),
                        unit="pcs", base_qty=str(n), total_price=str(Decimal(str(total_price))),
                        purchased_on=purchased_on, created_at=now(), invoice_no=invoice_no,
                        transport_charge=str(Decimal(str(transport_charge))), landed_total=str(landed))
        inventory.change_stock(db, "bottle", b["id"], n, "purchase", "purchase", pid)
        db.execute("UPDATE bottles SET avg_cost_each=? WHERE id=?", (str(new_avg), b["id"]))
    return pid


def buy_supply(db, supplier_id, supply_id, qty, total_price, purchased_on, transport_charge=0, invoice_no=None):
    _check(db, supplier_id, total_price)
    sp = db.one("SELECT * FROM supplies WHERE id=?", (supply_id,))
    if not sp:
        raise ValueError("unknown supply item")
    n = Decimal(str(qty))
    if n <= 0 or n != n.to_integral_value():
        raise ValueError("quantity must be a positive whole number")
    landed = _landed(total_price, transport_charge)
    with db.tx():
        new_avg = weighted_avg_cost(sp["stock_qty"], sp["avg_cost_each"], n, landed)
        pid = db.insert("purchases", supplier_id=supplier_id, kind="supply", item_id=supply_id, qty=str(n),
                        unit="pcs", base_qty=str(n), total_price=str(Decimal(str(total_price))),
                        purchased_on=purchased_on, created_at=now(), invoice_no=invoice_no,
                        transport_charge=str(Decimal(str(transport_charge))), landed_total=str(landed))
        inventory.change_stock(db, "supply", supply_id, n, "purchase", "purchase", pid)
        db.execute("UPDATE supplies SET avg_cost_each=? WHERE id=?", (str(new_avg), supply_id))
    return pid


def record_purchase_invoice(db, supplier_id, invoice_no, purchased_on, lines, transport_charge=0,
                            paid_amount=0, pay_method="cash"):
    """One supplier invoice with several lines. Transport is shared across lines in proportion to their price
    (so every item's landed cost includes its share). All lines + stock + optional payment succeed together or not at all.
    line = {"kind": "oil"|"bottle"|"supply", "item_id": id, "qty": n, "unit": "kg|g|mg|ml|l" (oil only), "total_price": x}"""
    if not lines:
        raise ValueError("an invoice needs at least one line")
    transport = Decimal(str(transport_charge))
    if transport < 0:
        raise ValueError("transport charge cannot be negative")
    prices = [Decimal(str(l["total_price"])) for l in lines]
    if any(p < 0 for p in prices):
        raise ValueError("price cannot be negative")
    base = sum(prices)
    shares, used = [], Decimal("0")
    for i, pr in enumerate(prices):
        if i == len(prices) - 1:
            share = transport - used
        elif base > 0:
            share = (transport * pr / base).quantize(Decimal("0.01"))
        else:
            share = (transport / len(prices)).quantize(Decimal("0.01"))
        shares.append(share); used += share
    ids = []
    with db.tx():
        for l, share in zip(lines, shares):
            kind = l["kind"]
            if kind == "oil":
                ids.append(buy_oil(db, supplier_id, int(l["item_id"]), l["qty"], l.get("unit", "g"), l["total_price"],
                                   purchased_on, share, invoice_no))
            elif kind == "bottle":
                b = db.one("SELECT size_ml FROM bottles WHERE id=?", (int(l["item_id"]),))
                if not b:
                    raise ValueError("unknown bottle size")
                ids.append(buy_bottles(db, supplier_id, b["size_ml"], l["qty"], l["total_price"], purchased_on, share, invoice_no))
            elif kind == "supply":
                ids.append(buy_supply(db, supplier_id, int(l["item_id"]), l["qty"], l["total_price"], purchased_on, share, invoice_no))
            else:
                raise ValueError("line kind must be oil, bottle or supply")
        if Decimal(str(paid_amount)) > 0:
            add_payment(db, supplier_id, paid_amount, purchased_on, pay_method, f"paid with invoice {invoice_no or ''}".strip())
    return ids


PAY_METHODS = ("cash", "upi", "bank_transfer", "cheque", "other")


def add_payment(db, supplier_id, amount, paid_on, method="cash", note=None):
    if not db.one("SELECT id FROM suppliers WHERE id=?", (supplier_id,)):
        raise ValueError("unknown supplier")
    amt = Decimal(str(amount))
    if amt <= 0:
        raise ValueError("payment amount must be positive")
    if method not in PAY_METHODS:
        raise ValueError("method must be one of: " + ", ".join(PAY_METHODS))
    from datetime import datetime
    try:
        datetime.strptime(paid_on, "%Y-%m-%d")
    except ValueError:
        raise ValueError("date must look like 2026-11-07")
    with db.tx():
        return db.insert("supplier_payments", supplier_id=supplier_id, paid_on=paid_on, amount=str(money(amt)),
                         method=method, note=note, created_at=now())


def list_payments(db, supplier_id=None):
    if supplier_id:
        return db.query("SELECT * FROM supplier_payments WHERE supplier_id=? ORDER BY paid_on DESC, id DESC", (supplier_id,))
    return db.query("SELECT * FROM supplier_payments ORDER BY paid_on DESC, id DESC")


def supplier_summary(db):
    """Per supplier: what was bought (landed cost incl. transport), what was paid, what is still owed."""
    out = []
    for s in db.query("SELECT * FROM suppliers ORDER BY name"):
        bought = sum((Decimal(r["landed_total"]) for r in db.query("SELECT landed_total FROM purchases WHERE supplier_id=?", (s["id"],))), Decimal("0"))
        paid = sum((Decimal(r["amount"]) for r in db.query("SELECT amount FROM supplier_payments WHERE supplier_id=?", (s["id"],))), Decimal("0"))
        out.append({**s, "total_purchased": str(money(bought)), "total_paid": str(money(paid)), "balance_due": str(money(bought - paid))})
    return out


def update_supplier(db, supplier_id, name=None, phone=None, notes=None):
    s = db.one("SELECT * FROM suppliers WHERE id=?", (supplier_id,))
    if not s:
        raise ValueError("unknown supplier")
    name = s["name"] if name is None else name.strip()
    if not name:
        raise ValueError("name required")
    with db.tx():
        db.execute("UPDATE suppliers SET name=?, phone=?, notes=? WHERE id=?",
                   (name, s["phone"] if phone is None else phone, s["notes"] if notes is None else notes, supplier_id))


def list_purchases(db):
    """Newest first, with supplier and item names, the per-unit rate and landed (all-in) cost."""
    sup = {r["id"]: r["name"] for r in db.query("SELECT id, name FROM suppliers")}
    oils = {r["id"]: r["name"] for r in db.query("SELECT id, name FROM oils")}
    bottles = {r["id"]: f"{r['size_ml']} ml bottle" for r in db.query("SELECT id, size_ml FROM bottles")}
    supplies = {r["id"]: r["name"] for r in db.query("SELECT id, name FROM supplies")}
    names = {"oil": oils, "bottle": bottles, "supply": supplies}
    rows = db.query("SELECT * FROM purchases ORDER BY id DESC")
    for r in rows:
        r["supplier_name"] = sup.get(r["supplier_id"], "")
        r["item_name"] = names[r["kind"]].get(r["item_id"], "")
        qty = Decimal(r["qty"])
        r["rate"] = str(money(Decimal(r["total_price"]) / qty)) if qty else "0.00"
    return rows
