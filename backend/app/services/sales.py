"""Point of sale. A sale uses FINISHED stock first (from production batches) and fills the rest from raw
materials (oil by density + bottle + caps/sprays/packing). Cost and tax are frozen on the sale.
All-or-nothing: if anything lacks stock, nothing is saved or deducted."""
import json
from decimal import Decimal
from uuid import uuid4

from app.core.costing import money
from app.core.units import oil_grams_for_bottle, q
from app.db import now, shop_today
from app.services import inventory, settings as settings_svc

PAYMENT_METHODS = ("cash", "card", "upi", "bank_transfer", "other")


class NotFound(LookupError):
    pass


def sell(db, items, customer_name="", payment_method="cash", discount=0, sold_on=None, utc_offset=330,
         customer_id=None, tax_rate=None):
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("payment_method must be one of: " + ", ".join(PAYMENT_METHODS))
    if not items:
        raise ValueError("a sale needs at least one item")
    wanted = {}
    for it in items:
        qty = Decimal(str(it["qty"]))
        if qty <= 0 or qty != qty.to_integral_value():
            raise ValueError("quantity must be a positive whole number")
        wanted[int(it["product_id"])] = wanted.get(int(it["product_id"]), 0) + int(qty)
    discount = Decimal(str(discount))
    if discount < 0:
        raise ValueError("discount cannot be negative")
    rate = Decimal(str(settings_svc.get(db, "tax_rate") if tax_rate is None else tax_rate))
    if not (0 <= rate <= 100):
        raise ValueError("tax rate must be between 0 and 100")
    cust = None
    if customer_id:
        cust = db.one("SELECT * FROM customers WHERE id=?", (int(customer_id),))
        if not cust:
            raise ValueError("unknown customer")
        customer_name = customer_name or cust["name"]

    lines = []
    for pid, qty in wanted.items():
        p = db.one("""SELECT p.*, o.density_g_per_ml AS dens, o.avg_cost_per_g AS oil_cost,
                      b.id AS bottle_id, b.avg_cost_each AS bottle_cost
                      FROM products p JOIN oils o ON o.id=p.oil_id JOIN bottles b ON b.size_ml=p.bottle_ml
                      WHERE p.id=?""", (pid,))
        if not p or not p["active"]:
            raise ValueError(f"unknown or inactive product {pid}")
        finished = min(qty, int(Decimal(p["stock_qty"])))
        raw = qty - finished
        comps = db.query("SELECT ps.supply_id, ps.qty_per_unit AS qty, s.avg_cost_each AS cost FROM product_supplies ps "
                         "JOIN supplies s ON s.id=ps.supply_id WHERE ps.product_id=?", (pid,))
        grams = q(oil_grams_for_bottle(p["bottle_ml"], p["dens"], p["oil_fraction"]) * raw)
        comp_use = [{"supply_id": c["supply_id"], "qty": c["qty"] * raw} for c in comps if raw > 0]
        cost = (Decimal(p["avg_cost_each"]) * finished + grams * Decimal(p["oil_cost"])
                + Decimal(p["bottle_cost"]) * raw + sum((Decimal(c["cost"]) * c["qty"] * raw for c in comps), Decimal("0")))
        lines.append(dict(p=p, qty=qty, finished=finished, raw=raw, grams=grams, comp_use=comp_use,
                          cost=money(cost), line_total=money(Decimal(p["price"]) * qty)))

    subtotal = money(sum((l["line_total"] for l in lines), Decimal("0")))
    if discount > subtotal:
        raise ValueError("discount cannot be more than the subtotal")
    taxable = subtotal - discount
    tax_amount = money(taxable * rate / 100)
    total = money(taxable + tax_amount)
    cost_total = money(sum((l["cost"] for l in lines), Decimal("0")))
    day = sold_on or shop_today(utc_offset)

    with db.tx():
        sale_id = db.insert("sales", invoice_no="TMP-" + uuid4().hex, sold_at=now(), sold_on=day,
                            customer_name=(customer_name or "").strip(), payment_method=payment_method,
                            subtotal=str(subtotal), discount=str(money(discount)), total=str(total),
                            cost_total=str(cost_total), customer_id=cust["id"] if cust else None,
                            tax_rate=str(rate), tax_amount=str(tax_amount))
        invoice_no = f"INV-{sale_id:06d}"
        db.execute("UPDATE sales SET invoice_no=? WHERE id=?", (invoice_no, sale_id))
        for l in lines:
            p = l["p"]
            db.insert("sale_items", sale_id=sale_id, product_id=p["id"], product_name=p["name"],
                      oil_id=p["oil_id"], bottle_id=p["bottle_id"], qty=l["qty"], unit_price=p["price"],
                      line_total=str(l["line_total"]), oil_grams=str(l["grams"]), cost_total=str(l["cost"]),
                      finished_qty=l["finished"], components_json=json.dumps(l["comp_use"]))
            try:
                if l["finished"]:
                    inventory.change_stock(db, "product", p["id"], -l["finished"], "sale", "sale", sale_id)
                if l["raw"]:
                    inventory.change_stock(db, "oil", p["oil_id"], -l["grams"], "sale", "sale", sale_id)
                    inventory.change_stock(db, "bottle", p["bottle_id"], -l["raw"], "sale", "sale", sale_id)
                    for c in l["comp_use"]:
                        inventory.change_stock(db, "supply", c["supply_id"], -c["qty"], "sale", "sale", sale_id)
            except ValueError as e:
                raise ValueError(f"{p['name']}: {e}")
    return sale_id


def get_sale(db, sale_id):
    s = db.one("SELECT * FROM sales WHERE id=?", (sale_id,))
    if not s:
        raise NotFound("sale not found")
    s["items"] = db.query("SELECT * FROM sale_items WHERE sale_id=? ORDER BY id", (sale_id,))
    return s


def list_sales(db, day=None):
    if day:
        return db.query("SELECT * FROM sales WHERE sold_on=? ORDER BY id DESC", (day,))
    return db.query("SELECT * FROM sales ORDER BY id DESC")


def void_sale(db, sale_id, reason=""):
    """Cancel a sale and put everything it used back in stock. Kept in history, excluded from reports."""
    s = get_sale(db, sale_id)
    if s["voided"]:
        raise ValueError("sale is already voided")
    with db.tx():
        db.execute("UPDATE sales SET voided=1, voided_at=?, void_reason=? WHERE id=?", (now(), reason, sale_id))
        for it in s["items"]:
            raw = it["qty"] - it["finished_qty"]
            if it["finished_qty"]:
                inventory.change_stock(db, "product", it["product_id"], it["finished_qty"], "sale_void", "sale", sale_id)
            if raw:
                inventory.change_stock(db, "oil", it["oil_id"], Decimal(it["oil_grams"]), "sale_void", "sale", sale_id)
                inventory.change_stock(db, "bottle", it["bottle_id"], raw, "sale_void", "sale", sale_id)
                for c in json.loads(it["components_json"] or "[]"):
                    inventory.change_stock(db, "supply", c["supply_id"], c["qty"], "sale_void", "sale", sale_id)
