import { useState } from "react";
import { api } from "../api.js";
import { CountModal, HistoryModal } from "../components/StockActions.jsx";
import { Empty, Field, Modal, PageHeader, Panel, State, num, rs, useAction, useLoad } from "../ui.jsx";

const TABS = [["bottle", "Bottles"], ["cap", "Caps"], ["spray", "Sprays"], ["packing", "Packing"]];
const WORD = { cap: "cap", spray: "spray", packing: "packing item" };

function AddModal({ tab, onClose, onDone }) {
  const [v, setV] = useState("");
  const run = useAction();
  async function save(e) {
    e.preventDefault();
    const ok = await run(() => tab === "bottle" ? api.post("/api/bottles", { size_ml: Number(v) }) : api.post("/api/supplies", { kind: tab, name: v }),
      "Added");
    if (ok) { onDone(); onClose(); }
  }
  return (
    <Modal title={tab === "bottle" ? "Add bottle size" : `Add ${WORD[tab]}`} onClose={onClose}>
      <form onSubmit={save} className="form">
        {tab === "bottle"
          ? <Field label="Size in ml"><input required type="number" min="1" step="1" value={v} onChange={(e) => setV(e.target.value)} autoFocus /></Field>
          : <Field label="Name"><input required value={v} onChange={(e) => setV(e.target.value)} autoFocus placeholder={tab === "cap" ? "Gold cap 12ml" : tab === "spray" ? "Spray pump" : "Gift box"} /></Field>}
        <div className="form-actions"><button type="button" className="btn ghost" onClick={onClose}>Cancel</button><button className="btn gold">Add</button></div>
      </form>
    </Modal>
  );
}

function RenameModal({ item, onClose, onDone }) {
  const [name, setName] = useState(item.name);
  const run = useAction();
  async function save(e) {
    e.preventDefault();
    if (await run(() => api.put(`/api/supplies/${item.id}`, { name }), "Renamed")) { onDone(); onClose(); }
  }
  return (
    <Modal title="Rename item" onClose={onClose}>
      <form onSubmit={save} className="form">
        <Field label="Name"><input required value={name} onChange={(e) => setName(e.target.value)} autoFocus /></Field>
        <div className="form-actions"><button type="button" className="btn ghost" onClick={onClose}>Cancel</button><button className="btn gold">Save</button></div>
      </form>
    </Modal>
  );
}

export default function BottleInventory() {
  const [tab, setTab] = useState("bottle");
  const { data: loaded, error, loading, reload } = useLoad(async () => ({ tab, rows: await api.get(tab === "bottle" ? "/api/bottles" : `/api/supplies?kind=${tab}`) }), [tab]);
  const data = loaded && loaded.tab === tab ? loaded.rows : null;   // never show another tab's rows while loading
  const [modal, setModal] = useState(null);
  const run = useAction();
  const nameOf = (i) => (tab === "bottle" ? `${i.size_ml} ml bottle` : i.name);
  const type = tab === "bottle" ? "bottle" : "supply";
  const hide = async (i) => { if (await run(() => api.put(`/api/supplies/${i.id}`, { active: false }), "Hidden")) reload(); };

  return (
    <>
      <PageHeader title="Bottles & Supplies" subtitle="Bottles, caps, sprays and packing are tracked separately">
        <a className="btn" href="#/purchases">Buy stock</a>
        <button className="btn gold" onClick={() => setModal({ type: "add" })}>{tab === "bottle" ? "Add bottle size" : `Add ${WORD[tab]}`}</button>
      </PageHeader>
      <div className="tabs" role="tablist">
        {TABS.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}
      </div>
      <State loading={loading || !data} error={error}>
        {data && (
          <Panel>
            {data.length === 0 ? <Empty>Nothing here yet.</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>{tab === "bottle" ? "Size" : "Item"}</th><th className="num">In stock</th><th className="num">Avg cost each</th><th className="num">Value</th><th /></tr></thead>
                <tbody>{data.map((i) => (
                  <tr key={i.id}><td>{nameOf(i)}</td><td className="num">{i.stock_qty}</td><td className="num">{rs(i.avg_cost_each)}</td>
                    <td className="num">{rs(Number(i.stock_qty) * Number(i.avg_cost_each))}</td>
                    <td className="actions">
                      <button className="btn sm" onClick={() => setModal({ type: "count", item: i })}>Count stock</button>
                      <button className="btn sm" onClick={() => setModal({ type: "history", item: i })}>History</button>
                      {tab !== "bottle" && <button className="btn sm" onClick={() => setModal({ type: "rename", item: i })}>Rename</button>}
                      {tab !== "bottle" && <button className="btn sm ghost" onClick={() => hide(i)}>Hide</button>}
                    </td></tr>
                ))}</tbody>
              </table></div>
            )}
            {tab !== "bottle" && <p className="muted small">Tell each product how many of these it uses in Products &rarr; Caps/packing. They are then deducted automatically.</p>}
          </Panel>
        )}
      </State>
      {modal?.type === "add" && <AddModal tab={tab} onClose={() => setModal(null)} onDone={reload} />}
      {modal?.type === "rename" && <RenameModal item={modal.item} onClose={() => setModal(null)} onDone={reload} />}
      {modal?.type === "count" && <CountModal type={type} item={modal.item} name={nameOf(modal.item)} unit="pcs" onClose={() => setModal(null)} onDone={reload} />}
      {modal?.type === "history" && <HistoryModal type={type} item={modal.item} name={nameOf(modal.item)} onClose={() => setModal(null)} />}
    </>
  );
}
