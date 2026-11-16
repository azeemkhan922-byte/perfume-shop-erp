import { api } from "../api.js";
import { Badge, Empty, PageHeader, Panel, State, Stat, num, rs, useLoad } from "../ui.jsx";

export default function Dashboard() {
  const { data: d, error, loading, reload } = useLoad(() => api.get("/api/reports/dashboard"), []);
  return (
    <>
      <PageHeader title="Dashboard" subtitle="How the shop is doing right now"><button className="btn ghost" onClick={reload}>Refresh</button></PageHeader>
      <State loading={loading} error={error}>
        {d && (
          <>
            <div className="stats-grid">
              <Stat label="Today's sales" value={rs(d.today.revenue)} />
              <Stat label="Today's expenses" value={rs(d.today.expenses)} />
              <Stat label="Today's gross profit" value={rs(d.today.gross_profit)} />
              <Stat label="Monthly sales" value={rs(d.month.revenue)} />
              <Stat label="Monthly net profit" value={rs(d.month.net_profit)} tone="gold" />
              <Stat label="Inventory value" value={rs(d.inventory_value)} />
            </div>
            <p className="muted">{d.today.sales_count} sales and {d.today.items_sold} items sold today; {d.month.sales_count} sales this month.</p>
            <div className="grid2">
              <Panel title="Low stock alerts">
                {d.low_stock.length === 0 ? <Empty>Everything is above its low-stock level.</Empty> : (
                  <div className="table-wrap"><table>
                    <thead><tr><th>Item</th><th className="num">In stock</th><th /></tr></thead>
                    <tbody>{d.low_stock.map((r) => (
                      <tr key={r.type + r.id}><td>{r.name} <span className="muted">({r.type})</span></td>
                        <td className="num">{num(r.qty)} {r.unit}</td><td><Badge tone="warn">{Number(r.qty) === 0 ? "Out" : "Low"}</Badge></td></tr>
                    ))}</tbody>
                  </table></div>
                )}
                <p className="muted small">Change the low-stock levels in Settings.</p>
              </Panel>
              <Panel title="Best-selling fragrances this month">
                {d.best_sellers.length === 0 ? <Empty>No sales yet this month.</Empty> : (
                  <div className="table-wrap"><table>
                    <thead><tr><th>Fragrance</th><th className="num">Pieces</th><th className="num">Sales</th></tr></thead>
                    <tbody>{d.best_sellers.map((b) => <tr key={b.fragrance}><td>{b.fragrance}</td><td className="num">{b.qty}</td><td className="num">{rs(b.revenue)}</td></tr>)}</tbody>
                  </table></div>
                )}
              </Panel>
            </div>
          </>
        )}
      </State>
    </>
  );
}
