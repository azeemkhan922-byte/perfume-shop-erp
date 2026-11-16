from datetime import datetime
from decimal import Decimal

from app.core.costing import money


def _date(v):
    datetime.strptime(v, "%Y-%m-%d")
    return v


def add_expense(db, spent_on, category, amount, note=None):
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("amount must be positive")
    if not category.strip():
        raise ValueError("category required")
    try:
        _date(spent_on)
    except ValueError:
        raise ValueError("date must look like 2026-11-07")
    with db.tx():
        return db.insert("expenses", spent_on=spent_on, category=category.strip(), amount=str(money(amount)), note=note)


def list_expenses(db, month=None):
    if month:
        return db.query("SELECT * FROM expenses WHERE spent_on LIKE ? ORDER BY spent_on DESC, id DESC", (month + "-%",))
    return db.query("SELECT * FROM expenses ORDER BY spent_on DESC, id DESC")


def delete_expense(db, expense_id):
    with db.tx():
        db.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
