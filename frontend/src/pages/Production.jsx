import { useState } from "react";
import { api } from "../api.js";
import { Empty, Field, PageHeader, Panel, State, num, rs, today, useAction, useLoad } from "../ui.jsx";

export default function Production() {
  const { data, error, loading, reload } = useLoad(async () => {
    const [products, oils, batches] = await Promise.all([api.get("/api/products"), api.get("/api/oils"), api.get("/api/batches")]);
    return { products, oils, batches };
  }, []);
  const [f, setF] = useState({ product_id: "", units: "", wastage_g: "0", other_cost: "0", made_on: today(), note: "" });
  const run = useAction();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const product = data?.products.find((p) => String(p.id) === String(f.product_id));
  const oil = product && data.oils.find((o) => o.id === product.oil_id);
  const needG = product ? Number(product.oil_grams) * Number(f.units || 0) + Number(f.wastage_g || 0) : 0;

  async function save(e) {
    e.preventDefault();
    if (await run(() => api.post("/api/batches", { ...f, product_id: Number(f.product_id), units: Number(f.units) }), "Batch recorded. Stock updated.")) {
      setF({ ...f, units: "", wastage_g: "0", other_cost: "0", note: "" }); reload();
    }
  }
  return (
    <>
      <PageHeader title="Production" subtitle="Fill bottles ahead of time. Oil, bottles, caps and packing are used up and wastage is recorded." />
      <State loading={loading} error={error}>
        {data && (
          <>
            <Panel title="New batch">
              {data.products.length === 0 ? <div className="notice">Create a product first.</div> : (
                <form onSubmit={save} className="form">
                  <div className="form-grid">
                    <Field label="Product"><select required value={f.product_id} onChange={set("product_id")}><option value="">Choose...</option>
                      {data.products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
                    <Field label="Bottles filled"><input required type="number" min="1" step="1" value={f.units} onChange={set("units")} /></Field>
                    <Field label="Wastage (g of oil)" hint="Spilled or lost oil. Its cost is added to the bottles' cost."><input type="number" min="0" step="0.001" value={f.wastage_g} onChange={set("wastage_g")} /></Field>
                    <Field label="Other costs (Rs.)" hint="Labour, labels etc."><input type="number" min="0" step="0.01" value={f.other_cost} onChange={set("other_cost")} /></Field>
                    <Field label="Date"><input required type="date" value={f.made_on} onChange={set("made_on")} /></Field>
                    <Field label="Note"><input value={f.note} onChange={set("note")} /></Field>
                  </div>
                  {product && (
                    <div className={`notice ${oil && needG > Number(oil.stock_g) ? "warn" : ""}`}>
                      Needs {num(needG)} g of {oil?.name} (you have {num(oil?.stock_g)} g), plus {f.units || 0} x {product.bottle_ml} ml bottles.
                    </div>
                  )}
                  <div className="form-actions"><button className="btn gold">Record batch</button></div>
                </form>
              )}
            </Panel>
            <Panel title="Batch history">
              {data.batches.length === 0 ? <Empty>No batches yet. You can also sell without batches: oil and bottles are then deducted at sale time.</Empty> : (
                <div className="table-wrap"><table>
                  <thead><tr><th>Date</th><th>Product</th><th className="num">Bottles</th><th className="num">Oil used (g)</th><th className="num">Wastage (g)</th><th className="num">Wastage cost</th><th className="num">Total cost</th><th className="num">Cost per bottle</th></tr></thead>
                  <tbody>{data.batches.map((b) => (
                    <tr key={b.id}><td>{b.made_on}</td><td>{b.product_name}</td><td className="num">{b.units}</td><td className="num">{num(b.oil_grams_used)}</td>
                      <td className="num">{num(b.wastage_g)}</td><td className="num">{rs(b.wastage_cost)}</td><td className="num">{rs(b.total_cost)}</td><td className="num">{rs(b.unit_cost)}</td></tr>
                  ))}</tbody></table></div>
              )}
            </Panel>
          </>
        )}
      </State>
    </>
  );
}
