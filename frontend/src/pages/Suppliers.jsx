import { useState } from "react";
import { api } from "../api.js";
import { Empty, Field, Modal, PageHeader, Panel, SearchBox, State, rs, today, useAction, useLoad } from "../ui.jsx";

function SupplierForm({ supplier, onClose, onDone }) {
  const [f, setF] = useState({ name: supplier?.name || "", phone: supplier?.phone || "", notes: supplier?.notes || "" });
  const run = useAction();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault();
    const ok = await run(() => supplier ? api.put(`/api/suppliers/${supplier.id}`, f) : api.post("/api/suppliers", f), supplier ? "Supplier updated" : "Supplier added");
    if (ok) { onDone(); onClose(); }
  }
  return (
    <Modal title={supplier ? "Edit supplier" : "Add supplier"} onClose={onClose}>
      <form onSubmit={save} className="form">
        <Field label="Name"><input required value={f.name} onChange={set("name")} autoFocus /></Field>
        <Field label="Phone"><input value={f.phone} onChange={set("phone")} /></Field>
        <Field label="Notes"><textarea rows="3" value={f.notes} onChange={set("notes")} /></Field>
        <div className="form-actions"><button type="button" className="btn ghost" onClick={onClose}>Cancel</button><button className="btn gold">Save</button></div>
      </form>
    </Modal>
  );
}

function PaymentForm({ supplier, onClose, onDone }) {
  const [f, setF] = useState({ amount: "", paid_on: today(), method: "cash", note: "" });
  const run = useAction();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault();
    if (await run(() => api.post("/api/supplier-payments", { supplier_id: supplier.id, ...f }), "Payment recorded")) { onDone(); onClose(); }
  }
  return (
    <Modal title={`Pay ${supplier.name}`} onClose={onClose}>
      <form onSubmit={save} className="form">
        <p className="muted">Currently owed: <b>{rs(supplier.balance_due)}</b></p>
        <div className="form-grid">
          <Field label="Amount (Rs.)"><input required type="number" step="0.01" min="0.01" value={f.amount} onChange={set("amount")} autoFocus /></Field>
          <Field label="Date"><input required type="date" value={f.paid_on} onChange={set("paid_on")} /></Field>
          <Field label="Method"><select value={f.method} onChange={set("method")}>
            <option value="cash">Cash</option><option value="upi">UPI</option><option value="bank_transfer">Bank transfer</option><option value="cheque">Cheque</option><option value="other">Other</option></select></Field>
          <Field label="Note"><input value={f.note} onChange={set("note")} /></Field>
        </div>
        <div className="form-actions"><button type="button" className="btn ghost" onClick={onClose}>Cancel</button><button className="btn gold">Record payment</button></div>
      </form>
    </Modal>
  );
}

function PaymentHistory({ supplier, onClose }) {
  const { data, error, loading } = useLoad(() => api.get(`/api/supplier-payments?supplier_id=${supplier.id}`), [supplier.id]);
  return (
    <Modal title={`Payments to ${supplier.name}`} onClose={onClose}>
      <State loading={loading} error={error}>
        {data && (data.length === 0 ? <Empty>No payments recorded.</Empty> : (
          <div className="table-wrap"><table><thead><tr><th>Date</th><th>Method</th><th className="num">Amount</th><th>Note</th></tr></thead>
            <tbody>{data.map((p) => <tr key={p.id}><td>{p.paid_on}</td><td>{p.method}</td><td className="num">{rs(p.amount)}</td><td>{p.note || ""}</td></tr>)}</tbody></table></div>
        ))}
      </State>
    </Modal>
  );
}

export default function Suppliers() {
  const { data, error, loading, reload } = useLoad(() => api.get("/api/suppliers"), []);
  const [q, setQ] = useState("");
  const [modal, setModal] = useState(null);
  const rows = (data || []).filter((s) => `${s.name} ${s.phone || ""}`.toLowerCase().includes(q.toLowerCase()));
  const owed = rows.reduce((t, s) => t + Number(s.balance_due), 0);
  return (
    <>
      <PageHeader title="Suppliers" subtitle="Who you buy from, what you owe, and what you have paid">
        <SearchBox value={q} onChange={setQ} placeholder="Search supplier" />
        <button className="btn gold" onClick={() => setModal({ type: "form" })}>Add supplier</button>
      </PageHeader>
      <State loading={loading} error={error}>
        {data && (
          <Panel>
            {rows.length === 0 ? <Empty>{data.length ? "Nothing matches your search." : "No suppliers yet."}</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Supplier</th><th>Phone</th><th className="num">Total bought</th><th className="num">Paid</th><th className="num">Balance due</th><th /></tr></thead>
                <tbody>{rows.map((s) => (
                  <tr key={s.id}><td>{s.name}</td><td>{s.phone || ""}</td><td className="num">{rs(s.total_purchased)}</td><td className="num">{rs(s.total_paid)}</td>
                    <td className={`num ${Number(s.balance_due) > 0 ? "neg" : ""}`}>{rs(s.balance_due)}</td>
                    <td className="actions">
                      <button className="btn sm gold" onClick={() => setModal({ type: "pay", s })}>Record payment</button>
                      <button className="btn sm" onClick={() => setModal({ type: "history", s })}>Payments</button>
                      <button className="btn sm" onClick={() => setModal({ type: "form", s })}>Edit</button>
                    </td></tr>
                ))}</tbody>
                <tfoot><tr><td colSpan="4">Total you owe suppliers</td><td className="num">{rs(owed)}</td><td /></tr></tfoot>
              </table></div>
            )}
            <p className="muted small">"Total bought" includes transport charges (landed cost).</p>
          </Panel>
        )}
      </State>
      {modal?.type === "form" && <SupplierForm supplier={modal.s} onClose={() => setModal(null)} onDone={reload} />}
      {modal?.type === "pay" && <PaymentForm supplier={modal.s} onClose={() => setModal(null)} onDone={reload} />}
      {modal?.type === "history" && <PaymentHistory supplier={modal.s} onClose={() => setModal(null)} />}
    </>
  );
}
