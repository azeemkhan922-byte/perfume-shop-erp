"""The whole HTTP API as plain Python (no web framework needed).
main.py plugs it into FastAPI for production; devserver.py runs it with the standard library for local use and testing.
Every route except /api/health and /api/login requires the owner's Bearer token."""
import json, re, sys, traceback
from datetime import datetime
from decimal import InvalidOperation

from app import config
from app.db import connect, shop_today
from app.services import (auth, backup, batches, catalog, customers, expenses, inventory, purchasing, reports,
                          sales, settings)
from app.services.pdf_invoice import build_invoice_pdf

MAX_BODY = 60 * 1024 * 1024
ROUTES = []


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


class Raw:
    """A non-JSON response (PDF, backup file)."""
    def __init__(self, content, content_type, headers=None):
        self.content, self.content_type, self.headers = content, content_type, headers or {}


class Ctx:
    def __init__(self, db, body, query, params):
        self.db, self.body, self.query, self.params = db, body, query, params

    def need(self, *names):
        missing = [n for n in names if n not in self.body or self.body[n] is None]
        if missing:
            raise ApiError(400, "missing field: " + ", ".join(missing))
        return [self.body[n] for n in names]

    def opt(self, name, default=None):
        v = self.body.get(name)
        return default if v is None else v


def route(method, pattern, public=False):
    regex = re.compile("^" + re.sub(r"\{(\w+):int\}", r"(?P<\1>\\d+)", re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern)) + "$")

    def deco(fn):
        ROUTES.append((method, regex, fn, public))
        return fn
    return deco


# ------------------------------------------------------------------ dispatch
def _json(status, payload, extra=None):
    h = {"Content-Type": "application/json; charset=utf-8"}
    h.update(extra or {})
    return status, h, json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")


def dispatch(method, path, query, body, authorization="", db_factory=None):
    """-> (status, headers, bytes). Never raises."""
    base = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    try:
        found, allowed = None, False
        for m, regex, fn, public in ROUTES:
            mt = regex.match(path)
            if mt:
                allowed = True
                if m == method:
                    found = (fn, public, {k: int(v) if v.isdigit() else v for k, v in mt.groupdict().items()})
                    break
        if not found:
            raise ApiError(405 if allowed else 404, "method not allowed" if allowed else "not found")
        fn, public, params = found
        if not public:
            token = authorization.removeprefix("Bearer ").strip() if authorization else ""
            if not auth.verify_token(token, config.SECRET_KEY):
                raise ApiError(401, "login required")
        if len(body) > MAX_BODY:
            raise ApiError(413, "request too large")
        data = {}
        if body:
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                raise ApiError(400, "request body is not valid JSON")
            if not isinstance(data, dict):
                raise ApiError(400, "request body must be a JSON object")
        db = (db_factory or (lambda: connect(config.DATABASE_URL)))()
        try:
            out = fn(Ctx(db, data, query, params))
        finally:
            try:
                db.conn.close()
            except Exception:
                pass
        if isinstance(out, Raw):
            return 200, {"Content-Type": out.content_type, **base, **out.headers}, out.content
        return _json(200, out, base)
    except ApiError as e:
        return _json(e.status, {"detail": e.message}, base)
    except auth.AuthError as e:
        return _json(401, {"detail": str(e)}, base)
    except sales.NotFound as e:
        return _json(404, {"detail": str(e)}, base)
    except (ValueError, inventory.StockError, KeyError, TypeError, InvalidOperation) as e:
        msg = f"missing field: {e.args[0]}" if isinstance(e, KeyError) else ("invalid number" if isinstance(e, InvalidOperation) else str(e))
        return _json(400, {"detail": msg}, base)
    except Exception as e:  # database constraint errors etc.
        text = str(e).lower()
        if "unique" in text or "duplicate" in text:
            return _json(409, {"detail": "already exists"}, base)
        if "foreign key" in text:
            return _json(400, {"detail": "refers to something that does not exist"}, base)
        traceback.print_exc(file=sys.stderr)
        return _json(500, {"detail": "internal server error"}, base)


def _today(ctx):
    return shop_today(config.SHOP_UTC_OFFSET_MINUTES)


# ------------------------------------------------------------------ public
@route("GET", "/api/health", public=True)
def health(ctx):
    if ctx.query.get("db") == "1":
        ctx.db.query("SELECT 1 AS ok")
        return {"status": "UP", "database": "OK"}
    return {"status": "UP"}


@route("POST", "/api/login", public=True)
def login(ctx):
    u, p = ctx.need("username", "password")
    return {"token": auth.login(ctx.db, str(u), str(p), config.SECRET_KEY, config.TOKEN_HOURS)}


@route("GET", "/api/me")
def me(ctx):
    s = settings.get_all(ctx.db)
    return {"ok": True, "shop_name": s["shop_name"]}


@route("POST", "/api/change-password")
def change_password(ctx):
    old, new = ctx.need("old_password", "new_password")
    try:
        auth.change_password(ctx.db, old, new)
    except auth.AuthError as e:      # 403, not 401: a wrong old password must not look like an expired session
        raise ApiError(403, str(e))
    return {"ok": True}


# ------------------------------------------------------------------ settings
@route("GET", "/api/settings")
def get_settings(ctx):
    return settings.get_all(ctx.db)


@route("PUT", "/api/settings")
def put_settings(ctx):
    return settings.set_many(ctx.db, ctx.body)


# ------------------------------------------------------------------ catalog
@route("GET", "/api/oils")
def oils(ctx):
    return catalog.list_oils(ctx.db)


@route("POST", "/api/oils")
def new_oil(ctx):
    n, d = ctx.need("name", "density_g_per_ml")
    return {"id": catalog.add_oil(ctx.db, n, d)}


@route("PUT", "/api/oils/{id:int}")
def edit_oil(ctx):
    catalog.update_oil(ctx.db, ctx.params["id"], ctx.body.get("name"), ctx.body.get("density_g_per_ml"), ctx.body.get("active"))
    return {"ok": True}


@route("GET", "/api/bottles")
def bottles(ctx):
    return catalog.list_bottles(ctx.db)


@route("POST", "/api/bottles")
def new_bottle(ctx):
    return {"id": catalog.add_bottle_size(ctx.db, ctx.need("size_ml")[0])}


@route("GET", "/api/supplies")
def supplies(ctx):
    return catalog.list_supplies(ctx.db, ctx.query.get("kind"))


@route("POST", "/api/supplies")
def new_supply(ctx):
    k, n = ctx.need("kind", "name")
    return {"id": catalog.add_supply(ctx.db, k, n)}


@route("PUT", "/api/supplies/{id:int}")
def edit_supply(ctx):
    catalog.update_supply(ctx.db, ctx.params["id"], ctx.body.get("name"), ctx.body.get("active"))
    return {"ok": True}


@route("GET", "/api/products")
def products(ctx):
    return catalog.enrich_costs(ctx.db, catalog.search_products(ctx.db, ctx.query.get("q", ""), ctx.query.get("all") == "1"))


@route("POST", "/api/products")
def new_product(ctx):
    n, o, b, p = ctx.need("name", "oil_id", "bottle_ml", "price")
    return {"id": catalog.add_product(ctx.db, n, int(o), b, p, ctx.opt("oil_fraction", "1"), ctx.body.get("barcode"))}


@route("PUT", "/api/products/{id:int}")
def edit_product(ctx):
    b = ctx.body
    catalog.update_product(ctx.db, ctx.params["id"], b.get("name"), b.get("price"),
                           b["barcode"] if "barcode" in b else "__keep__", b.get("oil_fraction"), b.get("active"))
    return {"ok": True}


@route("GET", "/api/products/{id:int}/supplies")
def product_supplies(ctx):
    return catalog.get_product_supplies(ctx.db, ctx.params["id"])


@route("PUT", "/api/products/{id:int}/supplies")
def put_product_supplies(ctx):
    catalog.set_product_supplies(ctx.db, ctx.params["id"], ctx.need("items")[0])
    return {"ok": True}


# ------------------------------------------------------------------ suppliers & purchases
@route("GET", "/api/suppliers")
def suppliers(ctx):
    return purchasing.supplier_summary(ctx.db)


@route("POST", "/api/suppliers")
def new_supplier(ctx):
    return {"id": purchasing.add_supplier(ctx.db, ctx.need("name")[0], ctx.body.get("phone"), ctx.body.get("notes"))}


@route("PUT", "/api/suppliers/{id:int}")
def edit_supplier(ctx):
    purchasing.update_supplier(ctx.db, ctx.params["id"], ctx.body.get("name"), ctx.body.get("phone"), ctx.body.get("notes"))
    return {"ok": True}


@route("GET", "/api/supplier-payments")
def payments(ctx):
    sid = ctx.query.get("supplier_id")
    return purchasing.list_payments(ctx.db, int(sid) if sid else None)


@route("POST", "/api/supplier-payments")
def new_payment(ctx):
    s, a, d = ctx.need("supplier_id", "amount", "paid_on")
    return {"id": purchasing.add_payment(ctx.db, int(s), a, d, ctx.opt("method", "cash"), ctx.body.get("note"))}


@route("GET", "/api/purchases")
def purchases(ctx):
    return purchasing.list_purchases(ctx.db)


@route("POST", "/api/purchases/oil")
def buy_oil(ctx):
    s, o, q, u, t, d = ctx.need("supplier_id", "oil_id", "qty", "unit", "total_price", "purchased_on")
    return {"id": purchasing.buy_oil(ctx.db, int(s), int(o), q, u, t, d, ctx.opt("transport_charge", 0), ctx.body.get("invoice_no"))}


@route("POST", "/api/purchases/bottles")
def buy_bottles(ctx):
    s, z, q, t, d = ctx.need("supplier_id", "size_ml", "qty", "total_price", "purchased_on")
    return {"id": purchasing.buy_bottles(ctx.db, int(s), int(z), q, t, d, ctx.opt("transport_charge", 0), ctx.body.get("invoice_no"))}


@route("POST", "/api/purchases/supply")
def buy_supply(ctx):
    s, i, q, t, d = ctx.need("supplier_id", "supply_id", "qty", "total_price", "purchased_on")
    return {"id": purchasing.buy_supply(ctx.db, int(s), int(i), q, t, d, ctx.opt("transport_charge", 0), ctx.body.get("invoice_no"))}


@route("POST", "/api/purchases/invoice")
def purchase_invoice(ctx):
    s, d, lines = ctx.need("supplier_id", "purchased_on", "lines")
    ids = purchasing.record_purchase_invoice(ctx.db, int(s), ctx.body.get("invoice_no"), d, lines, ctx.opt("transport_charge", 0),
                                             ctx.opt("paid_amount", 0), ctx.opt("pay_method", "cash"))
    return {"ids": ids}


# ------------------------------------------------------------------ stock & production
@route("POST", "/api/stocktake")
def stocktake(ctx):
    t, i, c = ctx.need("item_type", "item_id", "counted")
    if t not in inventory.TABLES:
        raise ApiError(400, "item_type must be one of: " + ", ".join(inventory.TABLES))
    return {"balance": str(inventory.stocktake(ctx.db, t, int(i), c, ctx.opt("note", "stocktake")))}


@route("GET", "/api/stock/{item_type}/{item_id:int}/ledger")
def ledger(ctx):
    if ctx.params["item_type"] not in inventory.TABLES:
        raise ApiError(400, "item_type must be one of: " + ", ".join(inventory.TABLES))
    return inventory.ledger(ctx.db, ctx.params["item_type"], ctx.params["item_id"])


@route("GET", "/api/batches")
def list_batches(ctx):
    return batches.list_batches(ctx.db)


@route("POST", "/api/batches")
def new_batch(ctx):
    p, u = ctx.need("product_id", "units")
    return {"id": batches.make_batch(ctx.db, int(p), u, ctx.opt("wastage_g", 0), ctx.opt("other_cost", 0),
                                     ctx.body.get("made_on"), ctx.opt("note", ""), config.SHOP_UTC_OFFSET_MINUTES)}


# ------------------------------------------------------------------ customers
@route("GET", "/api/customers")
def list_customers(ctx):
    return customers.list_customers(ctx.db, ctx.query.get("q", ""))


@route("POST", "/api/customers")
def new_customer(ctx):
    return {"id": customers.add_customer(ctx.db, ctx.need("name")[0], ctx.body.get("phone"), ctx.body.get("address"), ctx.body.get("notes"))}


@route("PUT", "/api/customers/{id:int}")
def edit_customer(ctx):
    b = ctx.body
    customers.update_customer(ctx.db, ctx.params["id"], b.get("name"), b.get("phone"), b.get("address"), b.get("notes"), b.get("active"))
    return {"ok": True}


@route("GET", "/api/customers/{id:int}/history")
def customer_history(ctx):
    return customers.customer_history(ctx.db, ctx.params["id"])


# ------------------------------------------------------------------ sales
@route("POST", "/api/sales")
def new_sale(ctx):
    items = ctx.need("items")[0]
    if not isinstance(items, list):
        raise ApiError(400, "items must be a list")
    sid = sales.sell(ctx.db, items, ctx.opt("customer_name", ""), ctx.opt("payment_method", "cash"), ctx.opt("discount", 0),
                     ctx.body.get("sold_on"), config.SHOP_UTC_OFFSET_MINUTES, ctx.body.get("customer_id"), ctx.body.get("tax_rate"))
    return {"id": sid, "invoice_no": f"INV-{sid:06d}"}


@route("GET", "/api/sales")
def all_sales(ctx):
    rows = sales.list_sales(ctx.db, ctx.query.get("day"))
    q = (ctx.query.get("q") or "").strip().lower()
    if q:
        rows = [r for r in rows if q in r["invoice_no"].lower() or q in (r["customer_name"] or "").lower()]
    return rows[: int(ctx.query.get("limit", 500))]


@route("GET", "/api/sales/{id:int}")
def one_sale(ctx):
    return sales.get_sale(ctx.db, ctx.params["id"])


@route("POST", "/api/sales/{id:int}/void")
def void(ctx):
    sales.void_sale(ctx.db, ctx.params["id"], ctx.opt("reason", ""))
    return {"ok": True}


@route("GET", "/api/sales/{id:int}/invoice.pdf")
def invoice_pdf(ctx):
    sale = sales.get_sale(ctx.db, ctx.params["id"])
    cfg = settings.get_all(ctx.db)
    return Raw(build_invoice_pdf(sale, cfg["shop_name"], cfg), "application/pdf",
               {"Content-Disposition": f'inline; filename="{sale["invoice_no"]}.pdf"'})


# ------------------------------------------------------------------ expenses
@route("GET", "/api/expenses")
def all_expenses(ctx):
    return expenses.list_expenses(ctx.db, ctx.query.get("month"))


@route("POST", "/api/expenses")
def new_expense(ctx):
    d, c, a = ctx.need("spent_on", "category", "amount")
    return {"id": expenses.add_expense(ctx.db, d, c, a, ctx.body.get("note"))}


@route("DELETE", "/api/expenses/{id:int}")
def remove_expense(ctx):
    expenses.delete_expense(ctx.db, ctx.params["id"])
    return {"ok": True}


# ------------------------------------------------------------------ reports
@route("GET", "/api/reports/daily")
def daily(ctx):
    if "day" not in ctx.query:
        raise ApiError(400, "missing query: day")
    return reports.daily_report(ctx.db, ctx.query["day"])


@route("GET", "/api/reports/monthly")
def monthly(ctx):
    if "month" not in ctx.query:
        raise ApiError(400, "missing query: month")
    return reports.monthly_report(ctx.db, ctx.query["month"])


@route("GET", "/api/reports/dashboard")
def dashboard(ctx):
    return reports.dashboard_full(ctx.db, config.SHOP_UTC_OFFSET_MINUTES)


@route("GET", "/api/reports/stock")
def stock(ctx):
    return reports.stock_report(ctx.db)


# ------------------------------------------------------------------ backup / restore
@route("GET", "/api/backup")
def download_backup(ctx):
    name = f"azeem-backup-{_today(ctx)}.json"
    return Raw(backup.export_json(ctx.db), "application/json", {"Content-Disposition": f'attachment; filename="{name}"'})


@route("POST", "/api/restore")
def restore_backup(ctx):
    password, data = ctx.need("password", "backup")
    if not auth.confirm_password(ctx.db, str(password)):
        raise ApiError(403, "wrong password")
    try:
        return {"restored": backup.restore(ctx.db, data)}
    except backup.BackupError as e:
        raise ApiError(400, str(e))
