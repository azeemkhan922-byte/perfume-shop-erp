import { useState } from "react";
import { api, downloadText } from "../api.js";
import { Empty, Field, PageHeader, Panel, State, Stat, num, rs, thisMonth, today, toCsv, useLoad } from "../ui.jsx";

export default function Reports() {
  const [mode, setMode] = useState("monthly");
  const [day, setDay] = useState(today());
  const [month, setMonth] = useState(thisMonth());
  const { data: raw, error, loading } = useLoad(() => mode === "daily" ? api.get(`/api/reports/daily?day=${day}`) : api.get(`/api/reports/monthly?month=${month}`), [mode, day, month]);
  const r = raw && (mode === "daily" ? "day" in raw : "month" in raw) ? raw : null;   // ignore stale data from the other mode
  const { data: salesRaw } = useLoad(() => (mode === "daily" ? api.get(`/api/sales?day=${day}`) : Promise.resolve(null)), [mode, day]);
  const sales = mode === "daily" ? salesRaw : null;
  const csv = () => downloadText(toCsv(r.by_day, [
    { label: "Day", get: (x) => x.day }, { label: "Revenue", get: (x) => x.revenue }, { label: "Gross profit", get: (x) => x.gross_profit },
    { label: "Expenses", get: (x) => x.expenses }, { label: "Net profit", get: (x) => x.net_profit }]), `profit-${month}.csv`);

  return (
    <>
      <PageHeader title="Profit & Loss" subtitle="Revenue (without tax) minus the real cost of what was sold, minus expenses">
        <div className="tabs compact" role="tablist">
          <button role="tab" aria-selected={mode === "daily"} className={mode === "daily" ? "active" : ""} onClick={() => setMode("daily")}>Daily</button>
          <button role="tab" aria-selected={mode === "monthly"} className={mode === "monthly" ? "active" : ""} onClick={() => setMode("monthly")}>Monthly</button>
        </div>
        {mode === "daily" ? <Field label="Day"><input type="date" value={day} onChange={(e) => e.target.value && setDay(e.target.value)} /></Field>
          : <Field label="Month"><input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} /></Field>}
        {mode === "monthly" && <button className="btn" disabled={!r || !r.by_day || r.by_day.length === 0} onClick={csv}>Download CSV</button>}
      </PageHeader>
      <State loading={loading || !r} error={error}>
        {r && (
          <>
            <div className="stats-grid">
              <Stat label="Sales (revenue)" value={rs(r.revenue)} /><Stat label="Cost of goods sold" value={rs(r.cost_of_goods)} />
              <Stat label="Gross profit" value={rs(r.gross_profit)} /><Stat label="Expenses" value={rs(r.expenses)} />
              <Stat label="Net profit" value={rs(r.net_profit)} tone="gold" /><Stat label="Tax collected" value={rs(r.tax_collected)} />
            </div>
            <p className="muted">{r.sales_count} sales, {r.items_sold} items. Discounts given: {rs(r.discounts)}. Oil wastage in production: {num(r.wastage_g)} g ({rs(r.wastage_cost)}).</p>
            <div className="grid2">
              <Panel title="Expenses by category">
                {r.expenses_by_category.length === 0 ? <Empty>No expenses.</Empty> : (
                  <div className="table-wrap"><table><tbody>{r.expenses_by_category.map((c) => <tr key={c.category}><td>{c.category}</td><td className="num">{rs(c.amount)}</td></tr>)}</tbody></table></div>)}
              </Panel>
              <Panel title="Top products">
                {r.top_products.length === 0 ? <Empty>No sales.</Empty> : (
                  <div className="table-wrap"><table><tbody>{r.top_products.map((p) => <tr key={p.name}><td>{p.name}</td><td className="num">{p.qty} pcs</td></tr>)}</tbody></table></div>)}
              </Panel>
            </div>
            {mode === "monthly" && (
              <Panel title="Day by day">
                {r.by_day.length === 0 ? <Empty>No activity this month.</Empty> : (
                  <div className="table-wrap"><table>
                    <thead><tr><th>Day</th><th className="num">Sales</th><th className="num">Gross profit</th><th className="num">Expenses</th><th className="num">Net profit</th></tr></thead>
                    <tbody>{r.by_day.map((d) => <tr key={d.day}><td>{d.day}</td><td className="num">{rs(d.revenue)}</td><td className="num">{rs(d.gross_profit)}</td><td className="num">{rs(d.expenses)}</td><td className="num">{rs(d.net_profit)}</td></tr>)}</tbody></table></div>)}
              </Panel>
            )}
            {mode === "daily" && sales && (
              <Panel title={`Sales on ${day}`}>
                {sales.length === 0 ? <Empty>No sales on this day.</Empty> : (
                  <div className="table-wrap"><table>
                    <thead><tr><th>Invoice</th><th>Customer</th><th>Payment</th><th className="num">Total</th></tr></thead>
                    <tbody>{sales.map((s) => <tr key={s.id} className={s.voided ? "inactive" : ""}><td>{s.invoice_no}{s.voided ? " (cancelled)" : ""}</td><td>{s.customer_name || "Walk-in"}</td><td>{s.payment_method}</td><td className="num">{rs(s.total)}</td></tr>)}</tbody></table></div>)}
              </Panel>
            )}
          </>
        )}
      </State>
    </>
  );
}
