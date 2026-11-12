import { useEffect, useRef, useState } from "react";
import { api, openPdf } from "../api.js";
import { Empty, Field, PageHeader, Panel, State, rs, useAction, useLoad } from "../ui.jsx";

const r2 = (x) => Math.round(x * 100) / 100;

export default function POS() {
  const { data, error, loading, reload } = useLoad(async () => {
    const [products, customers, settings] = await Promise.all([api.get("/api/products"), api.get("/api/customers"), api.get("/api/settings")]);
    return { products, customers, settings };
  }, []);
  const [q, setQ] = useState("");
  const [cart, setCart] = useState([]);
  const [cust, setCust] = useState("");
  const [walkin, setWalkin] = useState("");
  const [pay, setPay] = useState("cash");
  const [discount, setDiscount] = useState("");
  const [done, setDone] = useState(null);
  const [busy, setBusy] = useState(false);
  const search = useRef(null);
  const run = useAction();
  useEffect(() => { search.current?.focus(); }, [data, done]);

  const matches = data ? data.products.filter((p) => `${p.name} ${p.oil_name} ${p.barcode || ""}`.toLowerCase().includes(q.trim().toLowerCase())) : [];
  const add = (p) => { setCart((c) => (c.some((l) => l.p.id === p.id) ? c.map((l) => (l.p.id === p.id ? { ...l, qty: l.qty + 1 } : l)) : [...c, { p, qty: 1 }])); setQ(""); search.current?.focus(); };
  const onSearchKey = (e) => {
    if (e.key !== "Enter" || !q.trim()) return;
    e.preventDefault();
    const exact = data.products.find((p) => p.barcode && p.barcode === q.trim());   // barcode scanners "type" the code and press Enter
    const pick = exact || matches[0];
    if (pick) add(pick); else setQ("");
  };
  const setQty = (id, qty) => setCart((c) => c.map((l) => (l.p.id === id ? { ...l, qty } : l)));

  const rate = Number(data?.settings.tax_rate || 0);
  const subtotal = r2(cart.reduce((s, l) => s + Number(l.p.price) * l.qty, 0));
  const disc = Math.min(Math.max(Number(discount || 0), 0), subtotal);
  const tax = r2((subtotal - disc) * rate / 100);
  const total = r2(subtotal - disc + tax);

  async function checkout() {
    setBusy(true);
    const out = await run(() => api.post("/api/sales", {
      items: cart.map((l) => ({ product_id: l.p.id, qty: l.qty })), customer_id: cust ? Number(cust) : undefined,
      customer_name: cust ? "" : walkin, payment_method: pay, discount: discount || 0,
    }));
    setBusy(false);
    if (out && out !== true) { setDone({ ...out, total }); setCart([]); setDiscount(""); setCust(""); setWalkin(""); reload(); }
  }

  if (done) {
    return (
      <>
        <PageHeader title="Sale complete" />
        <Panel>
          <div className="receipt">
            <div className="big-ok">Sale recorded</div>
            <p>Invoice <b>{done.invoice_no}</b> &middot; Total <b>{rs(done.total)}</b></p>
            <p className="muted">Oil, bottles and any caps/packing were deducted from stock automatically.</p>
            <div className="form-actions">
              <button className="btn gold" onClick={() => run(() => openPdf(`/api/sales/${done.id}/invoice.pdf`))}>Open PDF invoice</button>
              <button className="btn" onClick={() => setDone(null)}>New sale</button>
            </div>
          </div>
        </Panel>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Sales POS" subtitle="Search or scan, add to the bill, take payment" />
      <State loading={loading} error={error}>
        {data && (
          <div className="pos">
            <Panel title="Products">
              <input ref={search} className="search big" type="search" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onSearchKey}
                placeholder="Search product or scan barcode, then press Enter" aria-label="Search product or scan barcode" />
              {data.products.length === 0 ? <Empty>No products yet. Add products first.</Empty> : matches.length === 0 ? <Empty>No product matches "{q}".</Empty> : (
                <div className="tiles">{matches.map((p) => (
                  <button key={p.id} className="tile" onClick={() => add(p)}>
                    <b>{p.name}</b><span>{rs(p.price)}</span>
                    <small className="muted">{Number(p.stock_qty) > 0 ? `${p.stock_qty} ready` : p.oil_name}</small>
                  </button>
                ))}</div>
              )}
            </Panel>
            <Panel title="Current bill">
              {cart.length === 0 ? <Empty>The bill is empty. Click a product to add it.</Empty> : (
                <div className="table-wrap"><table className="cart">
                  <thead><tr><th>Item</th><th className="num">Qty</th><th className="num">Total</th><th /></tr></thead>
                  <tbody>{cart.map((l) => (
                    <tr key={l.p.id}><td>{l.p.name}<br /><small className="muted">{rs(l.p.price)} each</small></td>
                      <td className="num"><div className="stepper">
                        <button className="btn sm" aria-label={`Less ${l.p.name}`} onClick={() => setQty(l.p.id, Math.max(1, l.qty - 1))}>-</button>
                        <input aria-label={`Quantity ${l.p.name}`} type="number" min="1" step="1" value={l.qty} onChange={(e) => setQty(l.p.id, Math.max(1, Math.floor(Number(e.target.value) || 1)))} />
                        <button className="btn sm" aria-label={`More ${l.p.name}`} onClick={() => setQty(l.p.id, l.qty + 1)}>+</button></div></td>
                      <td className="num">{rs(Number(l.p.price) * l.qty)}</td>
                      <td><button className="btn sm ghost" aria-label={`Remove ${l.p.name}`} onClick={() => setCart(cart.filter((x) => x.p.id !== l.p.id))}>x</button></td></tr>
                  ))}</tbody></table></div>
              )}
              <div className="form-grid">
                <Field label="Customer"><select value={cust} onChange={(e) => setCust(e.target.value)}><option value="">Walk-in customer</option>
                  {data.customers.map((c) => <option key={c.id} value={c.id}>{c.name}{c.phone ? ` (${c.phone})` : ""}</option>)}</select></Field>
                {!cust && <Field label="Name on bill (optional)"><input value={walkin} onChange={(e) => setWalkin(e.target.value)} /></Field>}
                <Field label="Payment"><select value={pay} onChange={(e) => setPay(e.target.value)}>
                  <option value="cash">Cash</option><option value="upi">UPI</option><option value="card">Card</option><option value="bank_transfer">Bank transfer</option></select></Field>
                <Field label="Discount (Rs.)"><input type="number" min="0" step="0.01" value={discount} onChange={(e) => setDiscount(e.target.value)} placeholder="0" /></Field>
              </div>
              <div className="summary">
                <div><span>Subtotal</span><b>{rs(subtotal)}</b></div>
                <div><span>Discount</span><b>- {rs(disc)}</b></div>
                {rate > 0 && <div><span>{data.settings.tax_name} ({rate}%)</span><b>{rs(tax)}</b></div>}
                <div className="total"><span>Total to pay</span><b>{rs(total)}</b></div>
              </div>
              <div className="form-actions">
                <button className="btn ghost" disabled={cart.length === 0} onClick={() => setCart([])}>Clear bill</button>
                <button className="btn gold big" disabled={cart.length === 0 || busy || Number(discount || 0) > subtotal} onClick={checkout}>{busy ? "Saving..." : "Complete sale"}</button>
              </div>
            </Panel>
          </div>
        )}
      </State>
    </>
  );
}
