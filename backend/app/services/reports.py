"""Profit reports. Revenue and cost come from non-voided sales (cost frozen at sale time).
Stock purchases are NOT expenses here - their cost reaches profit when the stock is sold."""
from datetime import datetime
from decimal import Decimal

from app.core.costing import money
from app.db import shop_today


def _sum(rows, key):
    return money(sum((Decimal(r[key]) for r in rows), Decimal("0")))


def _period(db, like):
    sales = db.query("SELECT * FROM sales WHERE voided=0 AND sold_on LIKE ? ORDER BY sold_on, id", (like,))
    exp = db.query("SELECT * FROM expenses WHERE spent_on LIKE ?", (like,))
    tax = _sum(sales, "tax_amount")
    revenue, cogs, expenses = money(_sum(sales, "total") - tax), _sum(sales, "cost_total"), _sum(exp, "amount")
    by_cat = {}
    for e in exp:
        by_cat[e["category"]] = by_cat.get(e["category"], Decimal("0")) + Decimal(e["amount"])
    batches = db.query("SELECT wastage_g, wastage_cost FROM batches WHERE made_on LIKE ?", (like,))
    items = db.query("SELECT i.product_name, i.qty FROM sale_items i JOIN sales s ON s.id=i.sale_id "
                     "WHERE s.voided=0 AND s.sold_on LIKE ?", (like,))
    top = {}
    for r in items:
        top[r["product_name"]] = top.get(r["product_name"], 0) + r["qty"]
    return {
        "sales_count": len(sales), "items_sold": sum(top.values()),
        "discounts": str(_sum(sales, "discount")), "tax_collected": str(tax), "revenue": str(revenue), "cost_of_goods": str(cogs),
        "gross_profit": str(money(revenue - cogs)), "expenses": str(expenses),
        "net_profit": str(money(revenue - cogs - expenses)),
        "expenses_by_category": [{"category": c, "amount": str(money(a))} for c, a in sorted(by_cat.items(), key=lambda x: -x[1])],
        "wastage_g": str(sum((Decimal(b["wastage_g"]) for b in batches), Decimal("0")).quantize(Decimal("0.001"))),
        "wastage_cost": str(_sum(batches, "wastage_cost")),
        "top_products": [{"name": n, "qty": c} for n, c in sorted(top.items(), key=lambda x: -x[1])[:5]],
    }, sales, exp


def daily_report(db, day):
    datetime.strptime(day, "%Y-%m-%d")
    r, _, _ = _period(db, day)
    return {"day": day, **r}


def monthly_report(db, month):
    datetime.strptime(month, "%Y-%m")
    r, sales, exp = _period(db, month + "-%")
    days = sorted({s["sold_on"] for s in sales} | {e["spent_on"] for e in exp})
    by_day = []
    for d in days:
        dr, _, _ = _period(db, d)
        by_day.append({"day": d, "revenue": dr["revenue"], "gross_profit": dr["gross_profit"],
                       "expenses": dr["expenses"], "net_profit": dr["net_profit"]})
    return {"month": month, **r, "by_day": by_day}


def dashboard(db, utc_offset=330):
    today = shop_today(utc_offset)
    return {
        "today": daily_report(db, today), "month": monthly_report(db, today[:7]),
        "oils": [{"id": o["id"], "name": o["name"], "stock_g": o["stock_g"]}
                 for o in db.query("SELECT * FROM oils WHERE active=1 ORDER BY name")],
        "bottles": [{"size_ml": b["size_ml"], "stock_qty": b["stock_qty"]}
                    for b in db.query("SELECT * FROM bottles ORDER BY size_ml")],
    }


# ---------------- inventory value, low stock, best sellers, stock report ----------------
def _stock_rows(db):
    rows = []
    for o in db.query("SELECT * FROM oils WHERE active=1 ORDER BY name"):
        rows.append(dict(type="oil", id=o["id"], name=o["name"], qty=o["stock_g"], unit="g", avg_cost=o["avg_cost_per_g"]))
    for b in db.query("SELECT * FROM bottles ORDER BY size_ml"):
        rows.append(dict(type="bottle", id=b["id"], name=f"{b['size_ml']} ml bottle", qty=b["stock_qty"], unit="pcs", avg_cost=b["avg_cost_each"]))
    for s in db.query("SELECT * FROM supplies WHERE active=1 ORDER BY kind, name"):
        rows.append(dict(type=s["kind"], id=s["id"], name=s["name"], qty=s["stock_qty"], unit="pcs", avg_cost=s["avg_cost_each"]))
    for p in db.query("SELECT * FROM products WHERE active=1 ORDER BY name"):
        if Decimal(p["stock_qty"]) > 0:
            rows.append(dict(type="finished", id=p["id"], name=p["name"], qty=p["stock_qty"], unit="pcs", avg_cost=p["avg_cost_each"]))
    return rows


def stock_report(db):
    from app.services import settings as st
    cfg = st.get_all(db)
    limit = {"oil": cfg["low_stock_oil_g"], "bottle": cfg["low_stock_bottles"], "finished": cfg["low_stock_products"]}
    rows, total = _stock_rows(db), Decimal("0")
    for r in rows:
        value = Decimal(r["qty"]) * Decimal(r["avg_cost"])
        r["value"] = str(money(value))
        r["low"] = Decimal(r["qty"]) <= Decimal(limit.get(r["type"], cfg["low_stock_supplies"]))
        total += value
    return {"items": rows, "total_value": str(money(total)), "low_count": sum(1 for r in rows if r["low"])}


def low_stock(db):
    return [r for r in stock_report(db)["items"] if r["low"] and not (r["type"] == "finished" and Decimal(r["qty"]) == 0)]


def best_sellers(db, like, limit=5):
    """Best-selling FRAGRANCES (oils) in a period: pieces and revenue."""
    rows = db.query("SELECT o.name AS name, i.qty AS qty, i.line_total AS line_total FROM sale_items i "
                    "JOIN sales s ON s.id=i.sale_id JOIN oils o ON o.id=i.oil_id WHERE s.voided=0 AND s.sold_on LIKE ?", (like,))
    agg = {}
    for r in rows:
        a = agg.setdefault(r["name"], [0, Decimal("0")])
        a[0] += r["qty"]; a[1] += Decimal(r["line_total"])
    ranked = sorted(agg.items(), key=lambda x: (-x[1][0], x[0]))[:limit]
    return [{"fragrance": n, "qty": a[0], "revenue": str(money(a[1]))} for n, a in ranked]


def dashboard_full(db, utc_offset=330):
    d = dashboard(db, utc_offset)
    month = d["today"]["day"][:7]
    sr = stock_report(db)
    d.update(inventory_value=sr["total_value"], low_stock=[r for r in sr["items"] if r["low"] and not (r["type"] == "finished" and Decimal(r["qty"]) == 0)],
             best_sellers=best_sellers(db, month + "-%"))
    return d
