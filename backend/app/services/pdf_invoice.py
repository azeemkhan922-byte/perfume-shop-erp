"""Invoice PDF built with only the Python standard library (no paid or extra software).
Plain A4, Helvetica, gold accents. Currency is written as 'Rs.' because the built-in PDF fonts have no rupee sign."""
from decimal import Decimal

ROWS_PER_PAGE = 26
GOLD = "0.78 0.62 0.20"


def _esc(t) -> str:
    t = str(t).encode("latin-1", "replace").decode("latin-1")
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _w(text, size):  # approximate Helvetica width (digits are exactly 0.556 em)
    return sum(0.278 if c in ".,: -" else 0.556 for c in str(text)) * size


def _text(x, y, s, size=10, bold=False, right=False, color="0 0 0"):
    if right:
        x = x - _w(s, size)
    return f"BT /{'F2' if bold else 'F1'} {size} Tf {color} rg {x:.1f} {y:.1f} Td ({_esc(s)}) Tj ET\n"


def _line(x1, y1, x2, y2, width=0.8, color=GOLD):
    return f"{color} RG {width} w {x1} {y1} m {x2} {y2} l S\n"


def _page(sale, shop, items, page_no, pages, last, info):
    c = _text(50, 790, shop, 22, True) + _line(50, 780, 545, 780, 2.0)
    c += _text(545, 790, "INVOICE", 14, True, right=True, color=GOLD)
    sub = "  |  ".join(x for x in (info.get("shop_address", ""), info.get("shop_phone", "")) if x)
    if sub:
        c += _text(50, 767, sub[:90], 9, color="0.35 0.35 0.35")
    c += _text(50, 745, f"Invoice: {sale['invoice_no']}", 10, True)
    c += _text(50, 730, f"Date: {sale['sold_on']}", 10)
    c += _text(50, 715, f"Customer: {sale['customer_name'] or 'Walk-in'}", 10)
    c += _text(545, 745, f"Payment: {sale['payment_method']}", 10, right=True)
    if sale["voided"]:
        c += _text(545, 730, "VOIDED", 12, True, right=True, color="0.8 0 0")
    y = 680
    c += _text(50, y, "Item", 10, True) + _text(350, y, "Qty", 10, True, right=True)
    c += _text(450, y, "Price", 10, True, right=True) + _text(545, y, "Total", 10, True, right=True)
    c += _line(50, y - 6, 545, y - 6, 0.5)
    y -= 24
    for it in items:
        c += _text(50, y, it["product_name"][:48], 10) + _text(350, y, it["qty"], 10, right=True)
        c += _text(450, y, it["unit_price"], 10, right=True) + _text(545, y, it["line_total"], 10, right=True)
        y -= 18
    if last:
        y -= 6
        c += _line(300, y + 12, 545, y + 12, 0.5)
        c += _text(450, y, "Subtotal", 10, right=True) + _text(545, y, f"Rs. {sale['subtotal']}", 10, right=True)
        y -= 16
        c += _text(450, y, "Discount", 10, right=True) + _text(545, y, f"Rs. {sale['discount']}", 10, right=True)
        if Decimal(sale.get("tax_amount", "0") or "0") > 0:
            y -= 16
            label = f"{info.get('tax_name', 'Tax')} ({sale['tax_rate']}%)"
            c += _text(450, y, label, 10, right=True) + _text(545, y, f"Rs. {sale['tax_amount']}", 10, right=True)
        y -= 20
        c += _text(450, y, "TOTAL", 12, True, right=True) + _text(545, y, f"Rs. {sale['total']}", 12, True, right=True)
    c += _line(50, 50, 545, 50, 0.5)
    c += _text(50, 36, (info.get("invoice_footer") or f"Thank you for choosing {shop}.")[:80], 9)
    if last and info.get("upi_id"):
        c += _text(50, 22, f"UPI: {info['upi_id']}", 9, color=GOLD)
    c += _text(545, 36, f"Page {page_no} of {pages}", 9, right=True)
    return c


def build_invoice_pdf(sale: dict, shop_name: str = "AZEEM FRAGRANCES", info: dict = None) -> bytes:
    info = info or {}
    items = sale["items"]
    chunks = [items[i:i + ROWS_PER_PAGE] for i in range(0, max(len(items), 1), ROWS_PER_PAGE)] or [[]]
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"]
    kids = []
    for n, chunk in enumerate(chunks, 1):
        stream = _page(sale, shop_name, chunk, n, len(chunks), n == len(chunks), info).encode("latin-1", "replace")
        page_id, content_id = len(objs) + 1, len(objs) + 2
        kids.append(f"{page_id} 0 R")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content_id} 0 R "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
