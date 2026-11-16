"""Fragrances (oils), bottle sizes and sellable products."""
from decimal import Decimal

from app.core.units import oil_grams_for_bottle


def _pos(v, name):
    d = Decimal(str(v))
    if d <= 0:
        raise ValueError(f"{name} must be positive")
    return d


def add_oil(db, name, density_g_per_ml):
    if not name.strip():
        raise ValueError("name required")
    with db.tx():
        return db.insert("oils", name=name.strip(), density_g_per_ml=str(_pos(density_g_per_ml, "density")))


def set_density(db, oil_id, density):
    with db.tx():
        db.execute("UPDATE oils SET density_g_per_ml=? WHERE id=?", (str(_pos(density, "density")), oil_id))


def list_oils(db):
    return db.query("SELECT * FROM oils WHERE active=1 ORDER BY name")


def add_bottle_size(db, size_ml):
    with db.tx():
        return db.insert("bottles", size_ml=int(_pos(size_ml, "size")))


def list_bottles(db):
    return db.query("SELECT * FROM bottles ORDER BY size_ml")


def add_product(db, name, oil_id, bottle_ml, price, oil_fraction="1", barcode=None):
    f = Decimal(str(oil_fraction))
    if not (0 < f <= 1):
        raise ValueError("oil_fraction must be between 0 and 1")
    if not db.one("SELECT id FROM oils WHERE id=?", (oil_id,)):
        raise ValueError("unknown oil")
    if not db.one("SELECT id FROM bottles WHERE size_ml=?", (int(bottle_ml),)):
        raise ValueError("unknown bottle size; add it first")
    with db.tx():
        return db.insert("products", name=name.strip(), oil_id=oil_id, bottle_ml=int(bottle_ml),
                         oil_fraction=str(f), price=str(_pos(price, "price")), barcode=_barcode(barcode))


def set_price(db, product_id, price):
    with db.tx():
        db.execute("UPDATE products SET price=? WHERE id=?", (str(_pos(price, "price")), product_id))


def list_products(db):
    return db.query("SELECT * FROM products WHERE active=1 ORDER BY name")


def oil_grams_needed(db, product_id) -> Decimal:
    p = db.one("SELECT p.*, o.density_g_per_ml AS dens FROM products p JOIN oils o ON o.id=p.oil_id WHERE p.id=?",
               (product_id,))
    if not p:
        raise ValueError("unknown product")
    return oil_grams_for_bottle(p["bottle_ml"], p["dens"], p["oil_fraction"])


# ---------- edits, barcode, search ----------
def update_oil(db, oil_id, name=None, density_g_per_ml=None, active=None):
    row = db.one("SELECT * FROM oils WHERE id=?", (oil_id,))
    if not row:
        raise ValueError("unknown oil")
    name = row["name"] if name is None else name.strip()
    if not name:
        raise ValueError("name required")
    dens = row["density_g_per_ml"] if density_g_per_ml is None else str(_pos(density_g_per_ml, "density"))
    act = row["active"] if active is None else (1 if active else 0)
    with db.tx():
        db.execute("UPDATE oils SET name=?, density_g_per_ml=?, active=? WHERE id=?", (name, dens, act, oil_id))


def _barcode(v):
    v = (v or "").strip()
    return v or None


def update_product(db, product_id, name=None, price=None, barcode="__keep__", oil_fraction=None, active=None):
    p = db.one("SELECT * FROM products WHERE id=?", (product_id,))
    if not p:
        raise ValueError("unknown product")
    name = p["name"] if name is None else name.strip()
    if not name:
        raise ValueError("name required")
    price = p["price"] if price is None else str(_pos(price, "price"))
    frac = p["oil_fraction"]
    if oil_fraction is not None:
        f = Decimal(str(oil_fraction))
        if not (0 < f <= 1):
            raise ValueError("oil_fraction must be between 0 and 1")
        frac = str(f)
    code = p["barcode"] if barcode == "__keep__" else _barcode(barcode)
    act = p["active"] if active is None else (1 if active else 0)
    with db.tx():
        db.execute("UPDATE products SET name=?, price=?, barcode=?, oil_fraction=?, active=? WHERE id=?",
                   (name, price, code, frac, act, product_id))


def set_barcode(db, product_id, barcode):
    update_product(db, product_id, barcode=barcode)


def search_products(db, q="", include_inactive=False):
    """Name contains q, or barcode equals q. Returns finished stock and the oil name for display."""
    sql = ("SELECT p.*, o.name AS oil_name FROM products p JOIN oils o ON o.id=p.oil_id WHERE 1=1"
           + ("" if include_inactive else " AND p.active=1"))
    params = []
    q = (q or "").strip()
    if q:
        sql += " AND (LOWER(p.name) LIKE ? OR p.barcode = ?)"
        params += ["%" + q.lower() + "%", q]
    return db.query(sql + " ORDER BY p.name", params)


# ---------- caps / sprays / packing ----------
SUPPLY_KINDS = ("cap", "spray", "packing")


def add_supply(db, kind, name):
    if kind not in SUPPLY_KINDS:
        raise ValueError("kind must be one of: " + ", ".join(SUPPLY_KINDS))
    if not name.strip():
        raise ValueError("name required")
    with db.tx():
        return db.insert("supplies", kind=kind, name=name.strip())


def update_supply(db, supply_id, name=None, active=None):
    s = db.one("SELECT * FROM supplies WHERE id=?", (supply_id,))
    if not s:
        raise ValueError("unknown supply item")
    name = s["name"] if name is None else name.strip()
    if not name:
        raise ValueError("name required")
    with db.tx():
        db.execute("UPDATE supplies SET name=?, active=? WHERE id=?",
                   (name, s["active"] if active is None else (1 if active else 0), supply_id))


def list_supplies(db, kind=None):
    if kind:
        return db.query("SELECT * FROM supplies WHERE active=1 AND kind=? ORDER BY name", (kind,))
    return db.query("SELECT * FROM supplies WHERE active=1 ORDER BY kind, name")


def set_product_supplies(db, product_id, items):
    """items = [{"supply_id": 3, "qty": 1}, ...]  - what ONE finished unit of this product uses besides oil and bottle."""
    if not db.one("SELECT id FROM products WHERE id=?", (product_id,)):
        raise ValueError("unknown product")
    seen = {}
    for it in items:
        qty = Decimal(str(it["qty"]))
        if qty <= 0 or qty != qty.to_integral_value():
            raise ValueError("component quantity must be a positive whole number")
        if not db.one("SELECT id FROM supplies WHERE id=?", (int(it["supply_id"]),)):
            raise ValueError("unknown supply item")
        seen[int(it["supply_id"])] = int(qty)
    with db.tx():
        db.execute("DELETE FROM product_supplies WHERE product_id=?", (product_id,))
        for sid, qty in seen.items():
            db.insert("product_supplies", product_id=product_id, supply_id=sid, qty_per_unit=qty)


def get_product_supplies(db, product_id):
    return db.query("SELECT ps.supply_id, ps.qty_per_unit AS qty, s.name, s.kind FROM product_supplies ps "
                    "JOIN supplies s ON s.id=ps.supply_id WHERE ps.product_id=? ORDER BY s.kind, s.name", (product_id,))


def enrich_costs(db, rows):
    """Adds the CURRENT actual cost of one unfilled-from-raw unit (oil by density + bottle + caps/sprays/packing)
    and the margin to each product row."""
    from app.core.costing import money
    for r in rows:
        o = db.one("SELECT density_g_per_ml AS d, avg_cost_per_g AS c FROM oils WHERE id=?", (r["oil_id"],))
        b = db.one("SELECT avg_cost_each AS c FROM bottles WHERE size_ml=?", (r["bottle_ml"],))
        grams = oil_grams_for_bottle(r["bottle_ml"], o["d"], r["oil_fraction"])
        comps = db.query("SELECT ps.qty_per_unit AS qty, s.avg_cost_each AS c FROM product_supplies ps "
                         "JOIN supplies s ON s.id=ps.supply_id WHERE ps.product_id=?", (r["id"],))
        cost = grams * Decimal(o["c"]) + Decimal(b["c"]) + sum((Decimal(c["c"]) * c["qty"] for c in comps), Decimal("0"))
        r["oil_grams"] = str(grams)
        r["est_cost"] = str(money(cost))
        r["margin"] = str(money(Decimal(r["price"]) - cost))
    return rows
