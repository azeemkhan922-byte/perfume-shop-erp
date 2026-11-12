import { useState } from "react";
import { api } from "../api.js";
import { Confirm, Empty, Field, PageHeader, Panel, State, rs, thisMonth, today, useAction, useLoad } from "../ui.jsx";

const CATEGORIES = ["Rent", "Electricity", "Salary", "Transport", "Packaging", "Marketing", "Repairs", "Other"];

export default function Expenses() {
  const [month, setMonth] = useState(thisMonth());
  const { data, error, loading, reload } = useLoad(() => api.get(`/api/expenses?month=${month}`), [month]);
  const [f, setF] = useState({ spent_on: today(), category: "Rent", amount: "", note: "" });
  const [del, setDel] = useState(null);
  const run = useAction();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const total = (data || []).reduce((s, e) => s + Number(e.amount), 0);

  async function add(e) {
    e.preventDefault();
    if (await run(() => api.post("/api/expenses", f), "Expense added")) { setF({ ...f, amount: "", note: "" }); reload(); }
  }
  async function remove() {
    if (await run(() => api.del(`/api/expenses/${del.id}`), "Expense deleted")) { setDel(null); reload(); }
  }
  return (
    <>
      <PageHeader title="Expenses" subtitle="Shop running costs. Buying stock is not an expense: it is counted when stock is sold.">
        <Field label="Month"><input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} /></Field>
      </PageHeader>
      <Panel title="Add expense">
        <form onSubmit={add} className="form-grid inline-form">
          <Field label="Date"><input required type="date" value={f.spent_on} onChange={set("spent_on")} /></Field>
          <Field label="Category"><input required list="cats" value={f.category} onChange={set("category")} /><datalist id="cats">{CATEGORIES.map((c) => <option key={c} value={c} />)}</datalist></Field>
          <Field label="Amount (Rs.)"><input required type="number" step="0.01" min="0.01" value={f.amount} onChange={set("amount")} /></Field>
          <Field label="Note"><input value={f.note} onChange={set("note")} /></Field>
          <div className="field end"><button className="btn gold">Add expense</button></div>
        </form>
      </Panel>
      <State loading={loading} error={error}>
        {data && (
          <Panel title={`Expenses for ${month}`}>
            {data.length === 0 ? <Empty>No expenses recorded for this month.</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Date</th><th>Category</th><th>Note</th><th className="num">Amount</th><th /></tr></thead>
                <tbody>{data.map((e) => (
                  <tr key={e.id}><td>{e.spent_on}</td><td>{e.category}</td><td>{e.note || ""}</td><td className="num">{rs(e.amount)}</td>
                    <td className="actions"><button className="btn sm danger" onClick={() => setDel(e)}>Delete</button></td></tr>
                ))}</tbody>
                <tfoot><tr><td colSpan="3">Month total</td><td className="num">{rs(total)}</td><td /></tr></tfoot>
              </table></div>
            )}
          </Panel>
        )}
      </State>
      {del && <Confirm title="Delete expense?" message={`Delete ${del.category} ${rs(del.amount)} on ${del.spent_on}? This changes your profit figures.`} confirmText="Delete" danger onConfirm={remove} onClose={() => setDel(null)} />}
    </>
  );
}
