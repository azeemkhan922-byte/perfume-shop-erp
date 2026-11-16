import { useEffect, useState } from "react";
import ErrorBoundary from "./ErrorBoundary.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import POS from "./pages/POS.jsx";
import Invoices from "./pages/Invoices.jsx";
import Products from "./pages/Products.jsx";
import AttarInventory from "./pages/AttarInventory.jsx";
import BottleInventory from "./pages/BottleInventory.jsx";
import Production from "./pages/Production.jsx";
import Suppliers from "./pages/Suppliers.jsx";
import Purchases from "./pages/Purchases.jsx";
import Customers from "./pages/Customers.jsx";
import Expenses from "./pages/Expenses.jsx";
import Reports from "./pages/Reports.jsx";
import StockReports from "./pages/StockReports.jsx";
import Settings from "./pages/Settings.jsx";

export const NAV = [
  { group: "Overview", items: [["dashboard", "Dashboard", Dashboard]] },
  { group: "Selling", items: [["pos", "Sales POS", POS], ["invoices", "Invoices", Invoices], ["customers", "Customers", Customers]] },
  { group: "Stock", items: [["products", "Products", Products], ["attar", "Attar Inventory", AttarInventory],
    ["bottles", "Bottles & Supplies", BottleInventory], ["production", "Production", Production]] },
  { group: "Buying", items: [["suppliers", "Suppliers", Suppliers], ["purchases", "Purchases", Purchases]] },
  { group: "Money", items: [["expenses", "Expenses", Expenses], ["reports", "Profit & Loss", Reports], ["stock", "Stock Reports", StockReports]] },
  { group: "System", items: [["settings", "Settings", Settings]] },
];
const PAGES = Object.fromEntries(NAV.flatMap((g) => g.items.map(([id, label, C]) => [id, { label, C }])));

const routeFromHash = () => {
  const r = window.location.hash.replace(/^#\/?/, "");
  return PAGES[r] ? r : "dashboard";
};

export default function Layout({ onLogout }) {
  const [route, setRoute] = useState(routeFromHash());
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const h = () => { setRoute(routeFromHash()); setOpen(false); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);

  const { label, C } = PAGES[route];
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
        <div className="brand">AZEEM<br />FRAGRANCES</div>
        <div className="gold-rule" />
        <nav>
          {NAV.map((g) => (
            <div key={g.group} className="nav-group">
              <div className="nav-title">{g.group}</div>
              {g.items.map(([id, name]) => (
                <a key={id} href={`#/${id}`} className={id === route ? "active" : ""}>{name}</a>
              ))}
            </div>
          ))}
        </nav>
        <button className="btn ghost signout" onClick={onLogout}>Sign out</button>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <div className="main">
        <header className="topbar">
          <button className="btn ghost menu" onClick={() => setOpen(true)} aria-label="Open menu">Menu</button>
          <span className="crumb">{label}</span>
        </header>
        <main className="content">
          <ErrorBoundary key={route} resetLabel="Back to dashboard" onReset={() => { window.location.hash = "#/dashboard"; }}><C /></ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
