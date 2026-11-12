import { createContext, useCallback, useContext, useEffect, useState } from "react";

export const rs = (v) =>
  "Rs. " + Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const num = (v, d = 3) => Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: d });
export const today = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};
export const thisMonth = () => today().slice(0, 7);

// ---- loading data
export function useLoad(fn, deps = []) {
  const [state, set] = useState({ data: null, error: "", loading: true });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = useCallback(() => {
    set((s) => ({ ...s, loading: true }));
    return fn().then((data) => set({ data, error: "", loading: false }))
      .catch((e) => set({ data: null, error: e.message, loading: false }));
  }, deps);
  useEffect(() => { reload(); }, [reload]);
  return { ...state, reload };
}

// ---- toasts
const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((message, type = "ok") => {
    const id = Math.random();
    setItems((s) => [...s, { id, message, type }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), type === "error" ? 6000 : 3000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status">
        {items.map((t) => <div key={t.id} className={`toast ${t.type}`}>{t.message}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

// Runs an async action; shows its error as a toast. Returns the result or undefined.
export function useAction() {
  const toast = useToast();
  return useCallback(async (fn, successMessage) => {
    try {
      const out = await fn();
      if (successMessage) toast(successMessage);
      return out ?? true;
    } catch (e) {
      toast(e.message, "error");
      return undefined;
    }
  }, [toast]);
}

// ---- layout pieces
export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="page-header">
      <div><h1>{title}</h1>{subtitle && <p className="muted">{subtitle}</p>}</div>
      <div className="toolbar">{children}</div>
    </div>
  );
}

export function Panel({ title, children, actions }) {
  return (
    <section className="panel">
      {(title || actions) && <div className="panel-head"><h2>{title}</h2><div className="toolbar">{actions}</div></div>}
      {children}
    </section>
  );
}

export function Stat({ label, value, tone }) {
  return <div className={`stat ${tone || ""}`}><span>{label}</span><b>{value}</b></div>;
}

export function State({ loading, error, children }) {
  if (error) return <div className="error" role="alert">{error}</div>;
  if (!children) return loading ? <p className="muted">Loading...</p> : null;
  return children;
}

export function Empty({ children }) {
  return <p className="muted empty">{children}</p>;
}

export function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-label={title}>
        <div className="modal-head"><h2>{title}</h2><button className="btn ghost sm" onClick={onClose} aria-label="Close">x</button></div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function Field({ label, hint, children }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small className="muted">{hint}</small>}</label>;
}

export function Confirm({ title, message, confirmText = "Confirm", danger, onConfirm, onClose, children }) {
  return (
    <Modal title={title} onClose={onClose}>
      <p>{message}</p>
      {children}
      <div className="form-actions">
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        <button className={`btn ${danger ? "danger" : "gold"}`} onClick={onConfirm}>{confirmText}</button>
      </div>
    </Modal>
  );
}

export function SearchBox({ value, onChange, placeholder = "Search..." }) {
  return <input className="search" type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder} />;
}

export function Badge({ tone = "", children }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function toCsv(rows, columns) {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [columns.map((c) => esc(c.label)).join(","), ...rows.map((r) => columns.map((c) => esc(c.get(r))).join(","))].join("\n");
}
