import { useState } from "react";
import { api } from "../api.js";
import { CountModal, HistoryModal } from "../components/StockActions.jsx";
import { Empty, Field, Modal, PageHeader, Panel, SearchBox, State, num, rs, useAction, useLoad } from "../ui.jsx";

function OilForm({ oil, onClose, onDone }) {
  const [f, setF] = useState({ name: oil?.name || "", density: oil?.density_g_per_ml || "0.90" });
  const run = useAction();
  async function save(e) {
    e.preventDefault();
    const ok = await run(() => oil ? api.put(`/api/oils/${oil.id}`, { name: f.name, density_g_per_ml: f.density })
      : api.post("/api/oils", { name: f.name, density_g_per_ml: f.density }), oil ? "Fragrance updated" : "Fragrance added");
    if (ok) { onDone(); onClose(); }
  }
  return (
    <Modal title={oil ? "Edit fragrance" : "Add fragrance (attar)"} onClose={onClose}>
      <form onSubmit={save} className="form">
        <Field label="Name"><input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoFocus placeholder="Oudh Royal" /></Field>
        <Field label="Density (grams per 1 ml)" hint="Weigh 10 ml on a scale and divide by 10. Never assume 1 g = 1 ml. Changing it affects future sales and production only.">
          <input required type="number" step="0.001" min="0.001" value={f.density} onChange={(e) => setF({ ...f, density: e.target.value })} /></Field>
        <div className="form-actions"><button type="button" className="btn ghost" onClick={onClose}>Cancel</button><button className="btn gold">{oil ? "Save" : "Add fragrance"}</button></div>
      </form>
    </Modal>
  );
}

export default function AttarInventory() {
  const { data, error, loading, reload } = useLoad(() => api.get("/api/oils"), []);
  const [q, setQ] = useState("");
  const [modal, setModal] = useState(null);
  const run = useAction();
  const rows = (data || []).filter((o) => o.name.toLowerCase().includes(q.toLowerCase()));
  const hide = async (o) => { if (await run(() => api.put(`/api/oils/${o.id}`, { active: false }), "Fragrance hidden")) reload(); };
  const total = rows.reduce((s, o) => s + Number(o.stock_g) * Number(o.avg_cost_per_g), 0);

  return (
    <>
      <PageHeader title="Attar Inventory" subtitle="Raw attar oil, kept in grams (1 kg = 1000 g)">
        <SearchBox value={q} onChange={setQ} placeholder="Search fragrance" />
        <a className="btn" href="#/purchases">Buy stock</a>
        <button className="btn gold" onClick={() => setModal({ type: "form" })}>Add fragrance</button>
      </PageHeader>
      <State loading={loading} error={error}>
        {data && (
          <Panel>
            {rows.length === 0 ? <Empty>{data.length === 0 ? "No fragrances yet. Add your first attar." : "Nothing matches your search."}</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Fragrance</th><th className="num">Density g/ml</th><th className="num">Stock (g)</th><th className="num">Stock (kg)</th>
                  <th className="num">Avg cost / g</th><th className="num">Stock value</th><th /></tr></thead>
                <tbody>{rows.map((o) => (
                  <tr key={o.id}><td>{o.name}</td><td className="num">{o.density_g_per_ml}</td><td className="num">{num(o.stock_g)}</td>
                    <td className="num">{num(Number(o.stock_g) / 1000)}</td><td className="num">{rs(o.avg_cost_per_g)}</td>
                    <td className="num">{rs(Number(o.stock_g) * Number(o.avg_cost_per_g))}</td>
                    <td className="actions">
                      <button className="btn sm" onClick={() => setModal({ type: "count", oil: o })}>Count stock</button>
                      <button className="btn sm" onClick={() => setModal({ type: "history", oil: o })}>History</button>
                      <button className="btn sm" onClick={() => setModal({ type: "form", oil: o })}>Edit</button>
                      <button className="btn sm ghost" onClick={() => hide(o)}>Hide</button>
                    </td></tr>
                ))}</tbody>
                <tfoot><tr><td colSpan="5">Total value of attar in stock</td><td className="num">{rs(total)}</td><td /></tr></tfoot>
              </table></div>
            )}
          </Panel>
        )}
      </State>
      {modal?.type === "form" && <OilForm oil={modal.oil} onClose={() => setModal(null)} onDone={reload} />}
      {modal?.type === "count" && <CountModal type="oil" item={modal.oil} name={modal.oil.name} unit="g" kgOption onClose={() => setModal(null)} onDone={reload} />}
      {modal?.type === "history" && <HistoryModal type="oil" item={modal.oil} name={modal.oil.name} onClose={() => setModal(null)} />}
    </>
  );
}
