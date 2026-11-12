import { useState } from "react";
import { api, downloadText } from "../api.js";
import { Badge, Empty, PageHeader, Panel, State, Stat, num, rs, toCsv, useLoad } from "../ui.jsx";

const TYPE = { oil: "Attar oil", bottle: "Bottle", cap: "Cap", spray: "Spray", packing: "Packing", finished: "Filled bottles" };

export default function StockReports() {
  const { data, error, loading, reload } = useLoad(() => api.get("/api/reports/stock"), []);
  const [type, setType] = useState("all");
  const [low, setLow] = useState(false);
  const rows = data ? data.items.filter((i) => (type === "all" || i.type === type) && (!low || i.low)) : [];
  const csv = () => downloadText(toCsv(rows, [
    { label: "Type", get: (i) => TYPE[i.type] }, { label: "Item", get: (i) => i.name }, { label: "Quantity", get: (i) => i.qty },
    { label: "Unit", get: (i) => i.unit }, { label: "Average cost", get: (i) => i.avg_cost }, { label: "Value", get: (i) => i.value }]), "stock-report.csv");
  return (
    <>
      <PageHeader title="Stock Reports" subtitle="Everything in stock, what it is worth, and what is running low">
        <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Filter by type">
          <option value="all">All types</option>{Object.entries(TYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <label className="check"><input type="checkbox" checked={low} onChange={(e) => setLow(e.target.checked)} /> Low stock only</label>
        <button className="btn" onClick={reload}>Refresh</button>
        <button className="btn gold" disabled={rows.length === 0} onClick={csv}>Download CSV</button>
      </PageHeader>
      <State loading={loading} error={error}>
        {data && (
          <>
            <div className="stats-grid"><Stat label="Total inventory value" value={rs(data.total_value)} tone="gold" /><Stat label="Items low or out" value={data.low_count} /></div>
            <Panel>
              {rows.length === 0 ? <Empty>Nothing to show for this filter.</Empty> : (
                <div className="table-wrap"><table>
                  <thead><tr><th>Type</th><th>Item</th><th className="num">Quantity</th><th className="num">Average cost</th><th className="num">Value</th><th>Status</th></tr></thead>
                  <tbody>{rows.map((i) => (
                    <tr key={i.type + i.id}><td>{TYPE[i.type]}</td><td>{i.name}</td><td className="num">{num(i.qty)} {i.unit}</td><td className="num">{rs(i.avg_cost)}</td><td className="num">{rs(i.value)}</td>
                      <td>{i.low ? <Badge tone="warn">{Number(i.qty) === 0 ? "Out of stock" : "Low"}</Badge> : <Badge tone="ok">OK</Badge>}</td></tr>
                  ))}</tbody></table></div>
              )}
            </Panel>
          </>
        )}
      </State>
    </>
  );
}
