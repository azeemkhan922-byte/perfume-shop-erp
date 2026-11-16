"""Manufacturing batches: turn raw oil + bottles + caps/sprays/packing into FINISHED units of a product.
Wastage (spilled/lost oil) is recorded and its cost is absorbed into the finished units' cost."""
from decimal import Decimal, ROUND_HALF_UP

from app.core.costing import money, weighted_avg_cost
from app.core.units import oil_grams_for_bottle, q
from app.db import now, shop_today
from app.services import inventory

_C = Decimal("0.0001")


def make_batch(db, product_id, units, wastage_g=0, other_cost=0, made_on=None, note="", utc_offset=330):
    n = Decimal(str(units))
    if n <= 0 or n != n.to_integral_value():
        raise ValueError("units must be a positive whole number")
    n = int(n)
    waste, other = Decimal(str(wastage_g)), Decimal(str(other_cost))
    if waste < 0 or other < 0:
        raise ValueError("wastage and other cost cannot be negative")
    p = db.one("""SELECT p.*, o.density_g_per_ml AS dens, o.avg_cost_per_g AS oil_cost,
                  b.id AS bottle_id, b.avg_cost_each AS bottle_cost
                  FROM products p JOIN oils o ON o.id=p.oil_id JOIN bottles b ON b.size_ml=p.bottle_ml
                  WHERE p.id=?""", (product_id,))
    if not p:
        raise ValueError("unknown product")
    comps = db.query("SELECT ps.supply_id, ps.qty_per_unit AS qty, s.avg_cost_each AS cost, s.name FROM product_supplies ps "
                     "JOIN supplies s ON s.id=ps.supply_id WHERE ps.product_id=?", (product_id,))
    oil_for_units = q(oil_grams_for_bottle(p["bottle_ml"], p["dens"], p["oil_fraction"]) * n)
    oil_used = q(oil_for_units + waste)
    oil_cost = Decimal(p["oil_cost"])
    cost = (oil_used * oil_cost + Decimal(p["bottle_cost"]) * n
            + sum((Decimal(c["cost"]) * c["qty"] * n for c in comps), Decimal("0")) + other)
    total_cost = money(cost)
    unit_cost = (cost / n).quantize(_C, rounding=ROUND_HALF_UP)
    day = made_on or shop_today(utc_offset)
    with db.tx():
        bid = db.insert("batches", product_id=product_id, made_on=day, units=n, oil_grams_used=str(oil_used),
                        wastage_g=str(q(waste)), wastage_cost=str(money(waste * oil_cost)), other_cost=str(money(other)), total_cost=str(total_cost),
                        unit_cost=str(unit_cost), note=note, created_at=now())
        try:
            inventory.change_stock(db, "oil", p["oil_id"], -oil_used, "batch", "batch", bid)
            inventory.change_stock(db, "bottle", p["bottle_id"], -n, "batch", "batch", bid)
            for c in comps:
                inventory.change_stock(db, "supply", c["supply_id"], -(c["qty"] * n), "batch", "batch", bid)
        except ValueError as e:
            raise ValueError(f"{p['name']}: {e}")
        new_avg = weighted_avg_cost(p["stock_qty"], p["avg_cost_each"], n, cost)
        inventory.change_stock(db, "product", product_id, n, "batch", "batch", bid)
        db.execute("UPDATE products SET avg_cost_each=? WHERE id=?", (str(new_avg), product_id))
    return bid


def list_batches(db):
    return db.query("SELECT b.*, p.name AS product_name FROM batches b JOIN products p ON p.id=b.product_id ORDER BY b.id DESC")
