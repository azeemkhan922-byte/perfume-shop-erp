import { useState } from "react";
import { api, downloadFile } from "../api.js";
import { Confirm, Field, PageHeader, Panel, State, today, useAction, useLoad, useToast } from "../ui.jsx";

function ShopSettings({ initial, onSaved }) {
  const [f, setF] = useState(initial);
  const run = useAction();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault();
    if (await run(() => api.put("/api/settings", f), "Settings saved")) onSaved();
  }
  return (
    <form onSubmit={save} className="form">
      <Panel title="Shop and invoice">
        <div className="form-grid">
          <Field label="Shop name"><input required value={f.shop_name} onChange={set("shop_name")} /></Field>
          <Field label="Phone"><input value={f.shop_phone} onChange={set("shop_phone")} /></Field>
          <Field label="Address"><input value={f.shop_address} onChange={set("shop_address")} /></Field>
          <Field label="UPI ID (printed on invoices)"><input value={f.upi_id} onChange={set("upi_id")} placeholder="name@bank" /></Field>
        </div>
        <Field label="Invoice footer message"><input value={f.invoice_footer} onChange={set("invoice_footer")} /></Field>
      </Panel>
      <Panel title="Tax">
        <div className="form-grid">
          <Field label="Tax name"><input value={f.tax_name} onChange={set("tax_name")} /></Field>
          <Field label="Tax rate %" hint="0 = no tax. Added on top of the price after discount."><input type="number" min="0" max="100" step="0.01" value={f.tax_rate} onChange={set("tax_rate")} /></Field>
        </div>
      </Panel>
      <Panel title="Low-stock alert levels">
        <div className="form-grid">
          <Field label="Attar oil (grams)"><input type="number" min="0" value={f.low_stock_oil_g} onChange={set("low_stock_oil_g")} /></Field>
          <Field label="Bottles (pieces)"><input type="number" min="0" value={f.low_stock_bottles} onChange={set("low_stock_bottles")} /></Field>
          <Field label="Caps, sprays, packing (pieces)"><input type="number" min="0" value={f.low_stock_supplies} onChange={set("low_stock_supplies")} /></Field>
          <Field label="Filled bottles (pieces)"><input type="number" min="0" value={f.low_stock_products} onChange={set("low_stock_products")} /></Field>
        </div>
      </Panel>
      <div className="form-actions"><button className="btn gold">Save settings</button></div>
    </form>
  );
}

function Password() {
  const [f, setF] = useState({ old_password: "", new_password: "", again: "" });
  const run = useAction();
  const toast = useToast();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault();
    if (f.new_password !== f.again) return toast("The new passwords do not match", "error");
    if (await run(() => api.post("/api/change-password", { old_password: f.old_password, new_password: f.new_password }), "Password changed")) setF({ old_password: "", new_password: "", again: "" });
  }
  return (
    <Panel title="Change password">
      <form onSubmit={save} className="form">
        <div className="form-grid">
          <Field label="Current password"><input required type="password" autoComplete="current-password" value={f.old_password} onChange={set("old_password")} /></Field>
          <Field label="New password (10+ characters)"><input required type="password" minLength="10" autoComplete="new-password" value={f.new_password} onChange={set("new_password")} /></Field>
          <Field label="New password again"><input required type="password" minLength="10" autoComplete="new-password" value={f.again} onChange={set("again")} /></Field>
        </div>
        <div className="form-actions"><button className="btn gold">Change password</button></div>
      </form>
    </Panel>
  );
}

function Backup() {
  const run = useAction();
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState(false);
  async function restore() {
    let backup;
    try { backup = JSON.parse(await file.text()); } catch { setConfirm(false); return toast("That file is not a valid backup", "error"); }
    const out = await run(() => api.post("/api/restore", { password, backup }));
    setConfirm(false);
    if (out) { toast("Backup restored. Reloading..."); setTimeout(() => window.location.reload(), 1200); }
  }
  return (
    <Panel title="Backup and restore">
      <p className="muted">The backup file contains ALL your data (and your sign-in details). Keep it private. Download one regularly: free databases do not keep automatic backups.</p>
      <div className="form-actions left"><button className="btn gold" onClick={() => run(() => downloadFile("/api/backup", `azeem-backup-${today()}.json`), "Backup downloaded")}>Download backup</button></div>
      <hr />
      <h3>Restore from a backup file</h3>
      <p className="warn-text">Restoring REPLACES everything currently in the system with the contents of the file.</p>
      <div className="form-grid">
        <Field label="Backup file (.json)"><input type="file" accept=".json,application/json" onChange={(e) => setFile(e.target.files[0] || null)} /></Field>
        <Field label="Your password (to confirm)"><input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
      </div>
      <div className="form-actions left"><button className="btn danger" disabled={!file || !password} onClick={() => setConfirm(true)}>Restore backup</button></div>
      {confirm && <Confirm title="Replace all data?" message={`All current data will be replaced by "${file.name}". This cannot be undone. Download a backup of the current data first if unsure.`} confirmText="Yes, replace everything" danger onConfirm={restore} onClose={() => setConfirm(false)} />}
    </Panel>
  );
}

export default function Settings() {
  const { data, error, loading, reload } = useLoad(() => api.get("/api/settings"), []);
  return (
    <>
      <PageHeader title="Settings" subtitle="Shop details, tax, alerts, password and backups" />
      <State loading={loading} error={error}>{data && <ShopSettings initial={data} onSaved={reload} key={JSON.stringify(data)} />}</State>
      <Password />
      <Backup />
    </>
  );
}
