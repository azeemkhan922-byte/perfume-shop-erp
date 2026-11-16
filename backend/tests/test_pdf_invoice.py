import re, unittest
from tests.helpers import fresh_db
from app.services import catalog, purchasing, sales
from app.services.pdf_invoice import build_invoice_pdf


def check_structure(test, pdf: bytes):
    test.assertTrue(pdf.startswith(b"%PDF-1.4"))
    test.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
    start = int(re.search(rb"startxref\n(\d+)\n", pdf).group(1))
    test.assertTrue(pdf[start:].startswith(b"xref"))
    offs = re.findall(rb"(\d{10}) 00000 n ", pdf)
    for n, off in enumerate(offs, 1):
        test.assertTrue(pdf[int(off):].startswith(b"%d 0 obj" % n), f"object {n} offset wrong")
    return len(offs)


class TestPdf(unittest.TestCase):
    def make_sale(self, n_lines=1, **kw):
        db = fresh_db()
        oil = catalog.add_oil(db, "Oudh", "0.90")
        sup = purchasing.add_supplier(db, "S")
        purchasing.buy_oil(db, sup, oil, 5, "kg", 100000, "2026-11-01")
        purchasing.buy_bottles(db, sup, 6, 500, 5000, "2026-11-01")
        items = []
        for i in range(n_lines):
            items.append({"product_id": catalog.add_product(db, f"Oudh (Special) #{i}", oil, 6, 700), "qty": 1})
        sid = sales.sell(db, items, "Ali \\ (VIP)", "cash", 0, "2026-11-07")
        if kw.get("void"):
            sales.void_sale(db, sid)
        return sales.get_sale(db, sid)

    def test_valid_pdf_with_invoice_details(self):
        pdf = build_invoice_pdf(self.make_sale(), "AZEEM FRAGRANCES")
        self.assertEqual(check_structure(self, pdf), 6)  # catalog, pages, 2 fonts, page, content
        for needle in (b"AZEEM FRAGRANCES", b"INV-000001", b"Rs. 700.00", b"2026-11-07"):
            self.assertIn(needle, pdf)

    def test_special_characters_are_escaped(self):
        pdf = build_invoice_pdf(self.make_sale())
        self.assertIn(b"Customer: Ali \\\\ \\(VIP\\)", pdf)

    def test_many_items_make_multiple_pages(self):
        pdf = build_invoice_pdf(self.make_sale(n_lines=60))
        self.assertEqual(check_structure(self, pdf), 4 + 2 * 3)
        self.assertIn(b"/Count 3", pdf)
        self.assertIn(b"Page 3 of 3", pdf)

    def test_voided_marked_and_non_latin_does_not_crash(self):
        s = self.make_sale(void=True)
        s["customer_name"] = "علی"
        pdf = build_invoice_pdf(s)
        check_structure(self, pdf)
        self.assertIn(b"VOIDED", pdf)


if __name__ == "__main__":
    unittest.main()
