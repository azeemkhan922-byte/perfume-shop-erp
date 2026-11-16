"""Every stock change goes through change_stock(): it updates the balance AND writes a ledger line."""
from decimal import Decimal

from app.core.units import q, deduct_stock
from app.db import now

TABLES = {"oil": ("oils", "stock_g"), "bottle": ("bottles", "stock_qty"),
          "supply": ("supplies", "stock_qty"), "product": ("products", "stock_qty")}
WHOLE_UNITS = {"bottle": "bottles", "supply": "pieces", "product": "finished units"}  # counted in whole pieces


class StockError(ValueError):
    pass


def get_stock(db, item_type, item_id) -> Decimal:
    table, col = TABLES[item_type]
    row = db.one(f"SELECT {col} AS s FROM {table} WHERE id=?", (item_id,))
    if not row:
        raise StockError(f"{item_type} {item_id} not found")
    return Decimal(row["s"])


def change_stock(db, item_type, item_id, delta, kind, ref_type=None, ref_id=None, note=None) -> Decimal:
    delta = Decimal(str(delta))
    table, col = TABLES[item_type]
    with db.tx():
        cur = get_stock(db, item_type, item_id)
        if delta < 0 and item_type in WHOLE_UNITS:
            if cur < -delta:
                raise StockError(f"insufficient stock: have {cur} {WHOLE_UNITS[item_type]}, need {-delta}")
            new = cur + delta
        elif delta < 0:
            new = deduct_stock(cur, -delta)  # raises ValueError if it would go negative
        else:
            new = q(cur + delta)
        if item_type in WHOLE_UNITS:
            if delta != delta.to_integral_value():
                raise StockError("this item is counted in whole pieces")
            new = new.quantize(Decimal("1"))
        db.execute(f"UPDATE {table} SET {col}=? WHERE id=?", (str(new), item_id))
        db.insert("stock_movements", moved_at=now(), item_type=item_type, item_id=item_id, delta=str(delta),
                  balance=str(new), kind=kind, ref_type=ref_type, ref_id=ref_id, note=note)
    return new


def stocktake(db, item_type, item_id, counted, note="stocktake") -> Decimal:
    """Owner counted the real stock: set it and record the difference."""
    counted = Decimal(str(counted))
    if counted < 0:
        raise StockError("counted stock cannot be negative")
    with db.tx():
        diff = counted - get_stock(db, item_type, item_id)
        return change_stock(db, item_type, item_id, diff, "adjustment", note=note) if diff != 0 else counted


def ledger(db, item_type, item_id):
    return db.query("SELECT * FROM stock_movements WHERE item_type=? AND item_id=? ORDER BY id",
                    (item_type, item_id))
