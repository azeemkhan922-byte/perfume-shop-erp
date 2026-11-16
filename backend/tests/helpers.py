from app.db import connect
from app.schema import create_schema


def fresh_db():
    db = connect("sqlite:///:memory:")
    create_schema(db)
    return db


def seed(db):
    """Typical shop: Oudh (density 0.9), 1 kg bought at Rs 50,000 (50/g), 12 ml bottles at 40 each, 6 ml at 30 each."""
    from app.services import catalog, purchasing
    oil = catalog.add_oil(db, "Oudh", "0.90")
    sup = purchasing.add_supplier(db, "Haji & Sons", "0300")
    purchasing.buy_oil(db, sup, oil, 1, "kg", 50000, "2026-11-01")
    purchasing.buy_bottles(db, sup, 12, 30, 1200, "2026-11-01")
    purchasing.buy_bottles(db, sup, 6, 30, 900, "2026-11-01")
    p12 = catalog.add_product(db, "Oudh 12ml", oil, 12, 1300)
    p6 = catalog.add_product(db, "Oudh 6ml", oil, 6, 700)
    return dict(oil=oil, sup=sup, p12=p12, p6=p6)
