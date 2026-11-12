import { useState } from "react";
import { api } from "../api.js";
import { Empty, Field, Modal, State, num, useAction, useLoad } from "../ui.jsx";

// Owner counted the real stock: record the difference as an adjustment.
export function CountModal({ type, item, name, unit, kgOption, onClose, onDone }) {
  const [value, setValue] = useState(item.stock_g ?? item.stock_qty);
  const [u, setU] = useState("g");
  const [note, setNote] = useState("stocktake");
  const run = useAction();
  async function save(e) {
    e.preventDefault();
    const counted = u === "kg" ? (Number(value) * 1000).toFixed(3) : value;
    if (await run(() => api.post("/api/stocktake", { item_type: type, item_id: item.id, counted, note }), "Stock updated")) {
      onDone(); onClose();
    }
  }
  return (
    <Modal title={`Count stock: ${name}`} onClose={onClose}>
      <form onSubmit={save} className="form">
        <Field label={`Counted quantity (${kgOption ? u : unit})`} hint="What is physically on the shelf now. The difference is recorded as an adjustment.">
          <div className="inline">
            <input type="number" step="any" min="0" required value={value} onChange={(e) => setValue(e.target.value)} autoFocus />
            {kgOption && <select value={u} onChange={(e) => setU(e.target.value)} aria-label="Unit"><option value="g">g</option><option value="kg">kg</option></select>}
          </div>
        </Field>
        <Field label="Reason"><input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <div className="form-actions"><button type="button" className="btn ghost" onClick={onClose}>Cancel</button><button className="btn gold">Save count</button></div>
      </form>
    </Modal>
  );
}

const KIND = { purchase: "Purchase", sale: "Sale", sale_void: "Sale cancelled", adjustment: "Stock count", batch: "Production" };

export function HistoryModal({ type, item, name, onClose }) {
  const { data, error, loading } = useLoad(() => api.get(`/api/stock/${type}/${item.id}/ledger`), [type, item.id]);
  const rows = data ? [...data].reverse().slice(0, 200) : [];
  return (
    <Modal title={`Stock history: ${name}`} onClose={onClose} wide>
      <State loading={loading} error={error}>
        {data && (rows.length === 0 ? <Empty>No stock movements yet.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>When</th><th>What</th><th className="num">Change</th><th className="num">Balance</th><th>Note</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.id}><td>{r.moved_at.replace("T", " ").slice(0, 16)}</td><td>{KIND[r.kind] || r.kind}</td>
                <td className={`num ${Number(r.delta) < 0 ? "neg" : "pos"}`}>{Number(r.delta) > 0 ? "+" : ""}{num(r.delta)}</td>
                <td className="num">{num(r.balance)}</td><td>{r.note || ""}</td></tr>
            ))}</tbody>
          </table></div>
        ))}
      </State>
    </Modal>
  );
}
