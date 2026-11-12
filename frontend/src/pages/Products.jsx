import { useState } from "react";
import { api } from "../api.js";
import { Badge, Empty, Field, Modal, PageHeader, Panel, SearchBox, State, num, rs, useAction, useLoad } from "../ui.jsx";

function ProductForm({ product, oils, bottles, onClose, onDone }) {
  const edit = Boolean(product);
  const [f, setF] = useState({
    name: product?.name || "", oil_id: product?.oil_id || oils[0]?.id || "", bottle_ml: product?.bottle_ml || 12,
    price: product?.price || "", pct: product ? String(Number(product.oil_fraction) * 100) : "100", barcode: product?.barcode || "",
  });
  const run = useAction();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault();
    const fraction = String(Number(f.pct) / 100);
    const ok = await run(() => edit
      ? api.put(`/api/products/${product.id}`, { name: f.name, price: f.price, barcode: f.barcode, oil_fraction: fraction })
      : api.post("/api/products", { name: f.name, oil_id: Number(f.oil_id), bottle_ml: Number(f.bottle_ml), price: f.price, oil_fraction: fraction, barcode: f.barcode }),
    edit ? "Product updated" : "Product added");
    if (ok) { onDone(); onClose(); }
  }
  return (
    <Modal title={edit ? "Edit product" : "Add product"} onClose={onClose}>
      <form onSubmit={save} className="form">
        <Field label="Product name"><input required value={f.name} onChange={set("name")} placeholder="Oudh Royal 12ml" autoFocus /></Field>
        <div className="form-grid">
          <Field label="Fragrance (attar)"><select value={f.oil_id} onChange={set("oil_id")} disabled={edit} required>
            {oils.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></Field>
          <Field label="Bottle size"><select value={f.bottle_ml} onChange={set("bottle_ml")} disabled={edit}>
            {bottles.map((b) => <option key={b.id} value={b.size_ml}>{b.size_ml} ml</option>)}</select></Field>
          <Field label="Selling price (Rs.)"><input required type="number" step="0.01" min="0.01" value={f.price} onChange={set("price")} /></Field>
          <Field label="Oil strength %" hint="100 = pure attar; 25 = diluted"><input required type="number" step="any" min="1" max="100" value={f.pct} onChange={set("pct")} /></Field>
        </div>
        <Field label="Barcode (optional)" hint="Scan or type. A barcode scanner works like a keyboard in the POS search box."><input value={f.barcode} onChange={set("barcode")} /></Field>
        {edit && <p className="muted small">Fragrance and bottle size cannot change after creation. Create a new product instead.</p>}
        <div className="form-actions"><button type="button" className="btn ghost" onClick={onClose}>Cancel</button><button className="btn gold">{edit ? "Save" : "Add product"}</button></div>
      </form>
    </Modal>
  );
}

function ComponentsModal({ product, onClose }) {
  const { data, error, loading } = useLoad(async () => {
    const [supplies, current] = await Promise.all([api.get("/api/supplies"), api.get(`/api/products/${product.id}/supplies`)]);
    return { supplies, qty: Object.fromEntries(current.map((c) => [c.supply_id, String(c.qty)])) };
  }, [product.id]);
  const [qty, setQty] = useState(null);
  const run = useAction();
  const q = qty || data?.qty || {};
  async function save() {
    const items = Object.entries(q).filter(([, v]) => Number(v) > 0).map(([id, v]) => ({ supply_id: Number(id), qty: Number(v) }));
    if (await run(() => api.put(`/api/products/${product.id}/supplies`, { items }), "Components saved")) onClose();
  }
  return (
    <Modal title={`Caps, sprays & packing: ${product.name}`} onClose={onClose}>
      <State loading={loading} error={error}>
        {data && (data.supplies.length === 0 ? <Empty>No caps, sprays or packing items yet. Add them in Bottles & Supplies first.</Empty> : (
          <>
            <p className="muted small">How many of each does ONE bottle of this product use? They are deducted automatically on every sale or production batch and included in the cost.</p>
            <div className="table-wrap"><table><thead><tr><th>Item</th><th>Type</th><th className="num">Per bottle</th></tr></thead>
              <tbody>{data.supplies.map((s) => (
                <tr key={s.id}><td>{s.name}</td><td>{s.kind}</td>
                  <td className="num"><input className="qty" type="number" min="0" step="1" value={q[s.id] ?? ""} placeholder="0" aria-label={`${s.name} per bottle`}
                    onChange={(e) => setQty({ ...q, [s.id]: e.target.value })} /></td></tr>
              ))}</tbody></table></div>
            <div className="form-actions"><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn gold" onClick={save}>Save</button></div>
          </>
        ))}
      </State>
    </Modal>
  );
}

export default function Products() {
  const { data, error, loading, reload } = useLoad(async () => {
    const [products, oils, bottles] = await Promise.all([api.get("/api/products?all=1"), api.get("/api/oils"), api.get("/api/bottles")]);
    return { products, oils, bottles };
  }, []);
  const [q, setQ] = useState("");
  const [modal, setModal] = useState(null);
  const run = useAction();
  const oilName = (id) => data.oils.find((o) => o.id === id)?.name || "?";
  const rows = data ? data.products.filter((p) => `${p.name} ${p.barcode || ""} ${oilName(p.oil_id)}`.toLowerCase().includes(q.toLowerCase())) : [];
  const toggle = async (p) => { if (await run(() => api.put(`/api/products/${p.id}`, { active: !p.active }), p.active ? "Product hidden" : "Product shown")) reload(); };

  return (
    <>
      <PageHeader title="Products" subtitle="What you sell: a fragrance in a bottle size, with its price and real cost">
        <SearchBox value={q} onChange={setQ} placeholder="Search name, fragrance or barcode" />
        <button className="btn gold" onClick={() => setModal({ type: "form" })} disabled={!data || data.oils.length === 0}>Add product</button>
      </PageHeader>
      <State loading={loading} error={error}>
        {data && data.oils.length === 0 && <div className="notice">Add a fragrance in Attar Inventory first, then create products from it.</div>}
        {data && (
          <Panel>
            {rows.length === 0 ? <Empty>No products found.</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Product</th><th>Fragrance</th><th className="num">Oil/bottle</th><th className="num">Price</th><th className="num">Cost</th>
                  <th className="num">Margin</th><th className="num">Ready stock</th><th>Barcode</th><th /></tr></thead>
                <tbody>{rows.map((p) => (
                  <tr key={p.id} className={p.active ? "" : "inactive"}>
                    <td>{p.name} {!p.active && <Badge>Hidden</Badge>}</td><td>{oilName(p.oil_id)}</td>
                    <td className="num">{num(p.oil_grams)} g</td><td className="num">{rs(p.price)}</td><td className="num">{rs(p.est_cost)}</td>
                    <td className={`num ${Number(p.margin) < 0 ? "neg" : "pos"}`}>{rs(p.margin)}</td>
                    <td className="num">{p.stock_qty}</td><td>{p.barcode || ""}</td>
                    <td className="actions">
                      <button className="btn sm" onClick={() => setModal({ type: "form", product: p })}>Edit</button>
                      <button className="btn sm" onClick={() => setModal({ type: "parts", product: p })}>Caps/packing</button>
                      <button className="btn sm ghost" onClick={() => toggle(p)}>{p.active ? "Hide" : "Show"}</button>
                    </td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
            <p className="muted small">Cost = oil (by density, at your average purchase cost) + bottle + caps/packing. "Ready stock" = bottles already filled in production batches.</p>
          </Panel>
        )}
      </State>
      {modal?.type === "form" && <ProductForm product={modal.product} oils={data.oils} bottles={data.bottles} onClose={() => setModal(null)} onDone={reload} />}
      {modal?.type === "parts" && <ComponentsModal product={modal.product} onClose={() => { setModal(null); reload(); }} />}
    </>
  );
}
