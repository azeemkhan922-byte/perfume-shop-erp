import { useState } from "react";
import { api } from "../api.js";
import { Empty, Field, PageHeader, Panel, SearchBox, State, num, rs, today, useAction, useLoad } from "../ui.jsx";

const blank = () => ({ kind: "oil", item_id: "", qty: "", unit: "kg", total_price: "" });

function NewPurchase({ ref_, onSaved }) {
  const { suppliers, oils, bottles, supplies } = ref_;
  const [h, setH] = useState({ supplier_id: "", invoice_no: "", purchased_on: today(), transport_charge: "0", paid_amount: "0", pay_method: "cash" });
  const [lines, setLines] = useState([blank()]);
  const run = useAction();
  const items = (kind) => kind === "oil" ? oils.map((o) => [o.id, o.name]) : kind === "bottle" ? bottles.map((b) => [b.id, `${b.size_ml} ml bottle`]) : supplies.map((s) => [s.id, `${s.name} (${s.kind})`]);
  const setLine = (i, patch) => setLines(lines.map((l, k) => (k === i ? { ...l, ...patch } : l)));
  const goods = lines.reduce((s, l) => s + Number(l.total_price || 0), 0);
  const landed = goods + Number(h.transport_charge || 0);

  async function save(e) {
    e.preventDefault();
    const payload = { ...h, supplier_id: Number(h.supplier_id), lines: lines.map((l) => ({ kind: l.kind, item_id: Number(l.item_id), qty: l.qty, unit: l.unit, total_price: l.total_price })) };
    if (await run(() => api.post("/api/purchases/invoice", payload), "Purchase saved. Stock and costs updated.")) {
      setLines([blank()]); setH({ ...h, invoice_no: "", transport_charge: "0", paid_amount: "0" }); onSaved();
    }
  }
  const noData = suppliers.length === 0 ? "Add a supplier first." : oils.length + bottles.length + supplies.length === 0 ? "Add items to buy first." : "";
  return (
    <Panel title="New purchase invoice">
      {noData && <div className="notice">{noData} <a href="#/suppliers">Suppliers</a> &middot; <a href="#/attar">Attar</a></div>}
      <form onSubmit={save} className="form">
        <div className="form-grid">
          <Field label="Supplier"><select required value={h.supplier_id} onChange={(e) => setH({ ...h, supplier_id: e.target.value })}>
            <option value="">Choose...</option>{suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
          <Field label="Supplier invoice no."><input value={h.invoice_no} onChange={(e) => setH({ ...h, invoice_no: e.target.value })} /></Field>
          <Field label="Date"><input required type="date" value={h.purchased_on} onChange={(e) => setH({ ...h, purchased_on: e.target.value })} /></Field>
        </div>
        <div className="table-wrap"><table className="lines">
          <thead><tr><th>Type</th><th>Item</th><th className="num">Quantity</th><th>Unit</th><th className="num">Price for this line (Rs.)</th><th /></tr></thead>
          <tbody>{lines.map((l, i) => (
            <tr key={i}>
              <td><select aria-label="Type" value={l.kind} onChange={(e) => setLine(i, { kind: e.target.value, item_id: "", unit: e.target.value === "oil" ? "kg" : "pcs" })}>
                <option value="oil">Attar oil</option><option value="bottle">Bottles</option><option value="supply">Caps / sprays / packing</option></select></td>
              <td><select aria-label="Item" required value={l.item_id} onChange={(e) => setLine(i, { item_id: e.target.value })}>
                <option value="">Choose...</option>{items(l.kind).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></td>
              <td className="num"><input aria-label="Quantity" className="qty" required type="number" step="any" min="0.001" value={l.qty} onChange={(e) => setLine(i, { qty: e.target.value })} /></td>
              <td>{l.kind === "oil"
                ? <select aria-label="Unit" value={l.unit} onChange={(e) => setLine(i, { unit: e.target.value })}><option value="kg">kg</option><option value="g">g</option><option value="ml">ml</option></select>
                : "pcs"}</td>
              <td className="num"><input aria-label="Line price" className="qty wide" required type="number" step="0.01" min="0" value={l.total_price} onChange={(e) => setLine(i, { total_price: e.target.value })} /></td>
              <td><button type="button" className="btn sm ghost" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, k) => k !== i))} aria-label="Remove line">Remove</button></td>
            </tr>
          ))}</tbody></table></div>
        <button type="button" className="btn" onClick={() => setLines([...lines, blank()])}>Add another item</button>
        <div className="form-grid">
          <Field label="Transport charges (Rs.)" hint="Shared across the items by value and added to their cost"><input type="number" step="0.01" min="0" value={h.transport_charge} onChange={(e) => setH({ ...h, transport_charge: e.target.value })} /></Field>
          <Field label="Paid to supplier now (Rs.)"><input type="number" step="0.01" min="0" value={h.paid_amount} onChange={(e) => setH({ ...h, paid_amount: e.target.value })} /></Field>
          <Field label="Payment method"><select value={h.pay_method} onChange={(e) => setH({ ...h, pay_method: e.target.value })}>
            <option value="cash">Cash</option><option value="upi">UPI</option><option value="bank_transfer">Bank transfer</option><option value="cheque">Cheque</option><option value="other">Other</option></select></Field>
        </div>
        <div className="summary">
          <div><span>Goods</span><b>{rs(goods)}</b></div><div><span>Transport</span><b>{rs(h.transport_charge)}</b></div>
          <div className="total"><span>Total landed cost</span><b>{rs(landed)}</b></div><div><span>Still owed on this invoice</span><b>{rs(landed - Number(h.paid_amount || 0))}</b></div>
        </div>
        <div className="form-actions"><button className="btn gold" disabled={Boolean(noData)}>Save purchase and update stock</button></div>
      </form>
    </Panel>
  );
}

export default function Purchases() {
  const { data, error, loading, reload } = useLoad(async () => {
    const [suppliers, oils, bottles, supplies, purchases] = await Promise.all([api.get("/api/suppliers"), api.get("/api/oils"), api.get("/api/bottles"), api.get("/api/supplies"), api.get("/api/purchases")]);
    return { suppliers, oils, bottles, supplies, purchases };
  }, []);
  const [q, setQ] = useState("");
  const rows = data ? data.purchases.filter((p) => `${p.invoice_no || ""} ${p.supplier_name} ${p.item_name}`.toLowerCase().includes(q.toLowerCase())) : [];
  return (
    <>
      <PageHeader title="Purchases" subtitle="Buy stock: it is added to inventory and the average cost updates automatically" />
      <State loading={loading} error={error}>
        {data && <NewPurchase ref_={data} onSaved={reload} />}
        {data && (
          <Panel title="Purchase history" actions={<SearchBox value={q} onChange={setQ} placeholder="Search invoice, supplier, item" />}>
            {rows.length === 0 ? <Empty>No purchases found.</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Date</th><th>Invoice</th><th>Supplier</th><th>Item</th><th className="num">Quantity</th><th className="num">Rate</th><th className="num">Price</th><th className="num">Transport</th><th className="num">Landed cost</th></tr></thead>
                <tbody>{rows.map((p) => (
                  <tr key={p.id}><td>{p.purchased_on}</td><td>{p.invoice_no || ""}</td><td>{p.supplier_name}</td><td>{p.item_name}</td>
                    <td className="num">{num(p.qty)} {p.unit}</td><td className="num">{rs(p.rate)}/{p.unit}</td><td className="num">{rs(p.total_price)}</td>
                    <td className="num">{rs(p.transport_charge)}</td><td className="num">{rs(p.landed_total)}</td></tr>
                ))}</tbody></table></div>
            )}
          </Panel>
        )}
      </State>
    </>
  );
}
