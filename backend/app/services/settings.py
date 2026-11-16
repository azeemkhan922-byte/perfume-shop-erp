"""Owner-editable shop settings (stored as key/value text)."""
from decimal import Decimal, InvalidOperation

DEFAULTS = {
    "shop_name": "AZEEM FRAGRANCES", "shop_address": "", "shop_phone": "",
    "tax_name": "GST", "tax_rate": "0", "upi_id": "",
    "invoice_footer": "Thank you for choosing AZEEM FRAGRANCES.",
    "low_stock_oil_g": "100", "low_stock_bottles": "10", "low_stock_supplies": "10", "low_stock_products": "3",
}
NUMERIC = {"tax_rate", "low_stock_oil_g", "low_stock_bottles", "low_stock_supplies", "low_stock_products"}


def get_all(db) -> dict:
    out = dict(DEFAULTS)
    for r in db.query("SELECT key, value FROM settings"):
        if r["key"] in DEFAULTS:
            out[r["key"]] = r["value"]
    return out


def get(db, key):
    return get_all(db)[key]


def set_many(db, values: dict):
    clean = {}
    for k, v in values.items():
        if k not in DEFAULTS:
            raise ValueError(f"unknown setting: {k}")
        v = "" if v is None else str(v).strip()
        if k in NUMERIC:
            try:
                d = Decimal(v)
            except InvalidOperation:
                raise ValueError(f"{k} must be a number")
            if d < 0 or (k == "tax_rate" and d > 100):
                raise ValueError("tax_rate must be between 0 and 100" if k == "tax_rate" else f"{k} cannot be negative")
            v = format(d.normalize(), "f") if d != 0 else "0"
        elif k == "shop_name" and not v:
            raise ValueError("shop_name cannot be empty")
        clean[k] = v
    with db.tx():
        for k, v in clean.items():
            db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value", (k, v))
    return get_all(db)
