import { useState } from "react";
import { api, openPdf } from "../api.js";
import { Badge, Empty, Field, Modal, PageHeader, Panel, SearchBox, State, rs, useAction, useLoad } from "../ui.jsx";

function CustomerForm({ customer, onClose, onDone }) {
  const [f, setF] = useState({ name: customer?.name || "", phone: customer?.phone || "", address: customer?.address || "", notes: customer?.notes || "" });
  const run = useAction();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault();
    if (await run(() => customer ? api.put(`/api/customers/${customer.id}`, f) : api.post("/api/customers", f), customer ? "Customer updated" : "Customer added")) { onDone(); onClose(); }
  }
  return (
    <Modal title={customer ? "Edit customer" : "Add customer"} onClose={onClose}>
      <form onSubmit={save} className="form">
        <Field label="Name"><input required value={f.name} onChange={set("name")} autoFocus /></Field>
        <Field label="Phone"><input value={f.phone} onChange={set("phone")} /></Field>
        <Field label="Address"><input value={f.address} onChange={set("address")} /></Field>
        <Field label="Notes (e.g. favourite fragrances)"><textarea rows="3" value={f.notes} onChange={set("notes")} /></Field>
        <div className="form-actions"><button type="button" className="btn ghost" onClick={onClose}>Cancel</button><button className="btn gold">Save</button></div>
      </form>
    </Modal>
  );
}

function History({ customer, onClose }) {
  const { data, error, loading } = useLoad(() => api.get(`/api/customers/${customer.id}/history`), [customer.id]);
  const run = useAction();
  return (
    <Modal title={`Purchases by ${customer.name}`} onClose={onClose} wide>
      <State loading={loading} error={error}>
        {data && (data.length === 0 ? <Empty>No purchases yet.</Empty> : (
          <div className="table-wrap"><table><thead><tr><th>Invoice</th><th>Date</th><th>Payment</th><th className="num">Total</th><th /></tr></thead>
            <tbody>{data.map((s) => (
              <tr key={s.id}><td>{s.invoice_no} {s.voided ? <Badge tone="warn">Cancelled</Badge> : null}</td><td>{s.sold_on}</td><td>{s.payment_method}</td><td className="num">{rs(s.total)}</td>
                <td className="actions"><button className="btn sm" onClick={() => run(() => openPdf(`/api/sales/${s.id}/invoice.pdf`))}>Invoice PDF</button></td></tr>
            ))}</tbody></table></div>
        ))}
      </State>
    </Modal>
  );
}

export default function Customers() {
  const [q, setQ] = useState("");
  const { data, error, loading, reload } = useLoad(() => api.get(`/api/customers?q=${encodeURIComponent(q)}`), [q]);
  const [modal, setModal] = useState(null);
  const run = useAction();
  const remove = async (c) => { if (await run(() => api.put(`/api/customers/${c.id}`, { active: false }), "Customer removed from the list")) reload(); };
  return (
    <>
      <PageHeader title="Customers" subtitle="Optional: attach a customer to a sale to keep their purchase history">
        <SearchBox value={q} onChange={setQ} placeholder="Search name or phone" />
        <button className="btn gold" onClick={() => setModal({ type: "form" })}>Add customer</button>
      </PageHeader>
      <State loading={loading} error={error}>
        {data && (
          <Panel>
            {data.length === 0 ? <Empty>{q ? "No customers match." : "No customers yet. Walk-in sales do not need one."}</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Name</th><th>Phone</th><th>Notes</th><th className="num">Sales</th><th className="num">Total spent</th><th /></tr></thead>
                <tbody>{data.map((c) => (
                  <tr key={c.id}><td>{c.name}</td><td>{c.phone || ""}</td><td>{c.notes || ""}</td><td className="num">{c.sales_count}</td><td className="num">{rs(c.total_spent)}</td>
                    <td className="actions">
                      <button className="btn sm" onClick={() => setModal({ type: "history", c })}>History</button>
                      <button className="btn sm" onClick={() => setModal({ type: "form", c })}>Edit</button>
                      <button className="btn sm ghost" onClick={() => remove(c)}>Remove</button>
                    </td></tr>
                ))}</tbody></table></div>
            )}
          </Panel>
        )}
      </State>
      {modal?.type === "form" && <CustomerForm customer={modal.c} onClose={() => setModal(null)} onDone={reload} />}
      {modal?.type === "history" && <History customer={modal.c} onClose={() => setModal(null)} />}
    </>
  );
}
