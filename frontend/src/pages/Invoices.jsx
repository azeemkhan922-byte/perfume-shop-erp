import { useState } from "react";
import { api, openPdf } from "../api.js";
import { Badge, Confirm, Empty, Field, Modal, PageHeader, Panel, SearchBox, State, rs, useAction, useLoad } from "../ui.jsx";

function Detail({ id, onClose }) {
  const { data: s, error, loading } = useLoad(() => api.get(`/api/sales/${id}`), [id]);
  return (
    <Modal title="Invoice details" onClose={onClose} wide>
      <State loading={loading} error={error}>
        {s && (
          <>
            <p><b>{s.invoice_no}</b> &middot; {s.sold_on} &middot; {s.customer_name || "Walk-in"} &middot; {s.payment_method} {s.voided ? <Badge tone="warn">Cancelled: {s.void_reason || "no reason"}</Badge> : null}</p>
            <div className="table-wrap"><table>
              <thead><tr><th>Item</th><th className="num">Qty</th><th className="num">Price</th><th className="num">Total</th></tr></thead>
              <tbody>{s.items.map((i) => <tr key={i.id}><td>{i.product_name}</td><td className="num">{i.qty}</td><td className="num">{rs(i.unit_price)}</td><td className="num">{rs(i.line_total)}</td></tr>)}</tbody>
              <tfoot>
                <tr><td colSpan="3">Subtotal</td><td className="num">{rs(s.subtotal)}</td></tr>
                <tr><td colSpan="3">Discount</td><td className="num">{rs(s.discount)}</td></tr>
                {Number(s.tax_amount) > 0 && <tr><td colSpan="3">Tax ({s.tax_rate}%)</td><td className="num">{rs(s.tax_amount)}</td></tr>}
                <tr><td colSpan="3"><b>Total</b></td><td className="num"><b>{rs(s.total)}</b></td></tr>
              </tfoot></table></div>
          </>
        )}
      </State>
    </Modal>
  );
}

export default function Invoices() {
  const [q, setQ] = useState("");
  const [day, setDay] = useState("");
  const { data, error, loading, reload } = useLoad(() => api.get(`/api/sales?q=${encodeURIComponent(q)}${day ? `&day=${day}` : ""}`), [q, day]);
  const [view, setView] = useState(null);
  const [voiding, setVoiding] = useState(null);
  const [reason, setReason] = useState("");
  const run = useAction();
  async function doVoid() {
    if (await run(() => api.post(`/api/sales/${voiding.id}/void`, { reason }), "Sale cancelled. Stock restored.")) { setVoiding(null); setReason(""); reload(); }
  }
  return (
    <>
      <PageHeader title="Invoices" subtitle="All sales. Open the PDF bill or cancel a sale (stock goes back).">
        <SearchBox value={q} onChange={setQ} placeholder="Search invoice or customer" />
        <Field label="Day"><input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></Field>
        {day && <button className="btn ghost" onClick={() => setDay("")}>All days</button>}
      </PageHeader>
      <State loading={loading} error={error}>
        {data && (
          <Panel>
            {data.length === 0 ? <Empty>No sales found.</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Invoice</th><th>Date</th><th>Customer</th><th>Payment</th><th className="num">Total</th><th /></tr></thead>
                <tbody>{data.map((s) => (
                  <tr key={s.id} className={s.voided ? "inactive" : ""}>
                    <td>{s.invoice_no} {s.voided ? <Badge tone="warn">Cancelled</Badge> : null}</td><td>{s.sold_on}</td><td>{s.customer_name || "Walk-in"}</td><td>{s.payment_method}</td><td className="num">{rs(s.total)}</td>
                    <td className="actions">
                      <button className="btn sm" onClick={() => setView(s.id)}>View</button>
                      <button className="btn sm gold" onClick={() => run(() => openPdf(`/api/sales/${s.id}/invoice.pdf`))}>PDF</button>
                      {!s.voided && <button className="btn sm danger" onClick={() => setVoiding(s)}>Cancel sale</button>}
                    </td></tr>
                ))}</tbody></table></div>
            )}
          </Panel>
        )}
      </State>
      {view && <Detail id={view} onClose={() => setView(null)} />}
      {voiding && (
        <Confirm title={`Cancel ${voiding.invoice_no}?`} message="The sale is kept in history but removed from reports, and its oil, bottles and supplies go back into stock." confirmText="Cancel this sale" danger onConfirm={doVoid} onClose={() => setVoiding(null)}>
          <Field label="Reason"><input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. customer returned" /></Field>
        </Confirm>
      )}
    </>
  );
}
