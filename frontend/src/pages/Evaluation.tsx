import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, errMsg } from '../api'
import { ActionChip, Callout, Empty, ErrorBox, PageHeader, Spinner, Status, Table, Th } from '../components/ui'
import { ms, pct, useFetch } from '../hooks'

type M = Record<string, any>
const METRICS: [string, string][] = [
  ['violation_rate', 'Violation rate'], ['unsupported_figure_rate', 'Unsupported figures'], ['pii_leakage_rate', 'PII leakage'],
  ['injection_success_rate', 'Injection success'], ['mnpi_catch_rate', 'MNPI catch rate'], ['false_positive_rate', 'False positives'],
]

function UseCaseTable({ rows }: { rows: [string, M][] }) {
  return (
    <Table caption="Per use case, guard off versus on">
      <thead><tr><Th>Use case</Th><Th>Items</Th>{METRICS.map(([k, l]) => <Th key={k}>{l} off / on</Th>)}</tr></thead>
      <tbody className="divide-y divide-slate-200">
        {rows.map(([name, m]) => (
          <tr key={name}><th scope="row" className="td text-left font-medium">{name}</th><td className="td">{m.items}</td>
            {METRICS.map(([k]) => <td key={k} className="td whitespace-nowrap">{pct(m[`${k}_off`])} / {pct(m[`${k}_on`])}</td>)}</tr>
        ))}
      </tbody>
    </Table>
  )
}

export default function Evaluation() {
  const latest = useFetch<any>('eval-latest', () => api('/api/eval/latest'))
  const [run, setRun] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [fKind, setFKind] = useState('')
  const [fUse, setFUse] = useState('')
  const r = run || latest.data

  const go = async () => {
    setBusy(true); setErr(null)
    try { setRun(await api('/api/eval/run', { method: 'POST' })) } catch (e) { setErr(errMsg(e)) } finally { setBusy(false) }
  }
  const o: M | undefined = r?.results?.overall
  const chart = o ? METRICS.filter(([k]) => o[`${k}_off`] !== null && o[`${k}_off`] !== undefined || o[`${k}_on`] !== null && o[`${k}_on`] !== undefined)
    .map(([k, label]) => ({ metric: label, 'Guard off': o[`${k}_off`] === null ? 0 : +(o[`${k}_off`] * 100).toFixed(1), 'Guard on': o[`${k}_on`] === null ? 0 : +(o[`${k}_on`] * 100).toFixed(1) })) : []
  const na = o ? METRICS.filter(([k]) => o[`${k}_off`] == null && o[`${k}_on`] == null).map(([, l]) => l) : []
  const items: any[] = r?.items || []
  const kinds = [...new Set(items.map((i) => i.kind))]
  const uses = [...new Set(items.map((i) => i.use_case))]
  const shown = items.filter((i) => (!fKind || i.kind === fKind) && (!fUse || i.use_case === fUse))

  return (
    <div>
      <PageHeader title="Evaluation">
        <button type="button" className="btn-primary" disabled={busy} onClick={() => void go()}>{busy ? 'Running…' : 'Run evaluation'}</button>
      </PageHeader>
      <div aria-live="polite">
        {busy && <Spinner label="Running the evaluation dataset with the guard off and on. This takes a few seconds." />}
        {err && <ErrorBox message={err} />}
        {run && !busy && <Status>Evaluation finished.</Status>}
      </div>
      {latest.error && !r && <ErrorBox message={latest.error} onRetry={latest.reload} />}
      {latest.loading && <Spinner />}
      {!latest.loading && !r && !busy && <Empty>No evaluation has been run yet. Press Run evaluation.</Empty>}
      {r && o && (
        <>
          <div className="mb-4"><Callout tone={r.mock ? 'warn' : 'info'}>
            <div><strong>Model:</strong> {r.model} · <strong>Provider:</strong> {r.provider} · <strong>Mock:</strong> {r.mock ? 'yes' : 'no'} · engine {r.engine} · {r.dataset_items} items · run {r.ts}</div>
            <div className="mt-1">{r.note}</div>
          </Callout></div>

          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="card"><div className="text-xs text-slate-700">Average added latency</div><div className="text-2xl font-bold">{ms(o.avg_added_latency_ms)}</div></div>
            <div className="card"><div className="text-xs text-slate-700">Expected-action match</div><div className="text-2xl font-bold">{pct(o.expected_action_match)}</div></div>
            <div className="card"><div className="text-xs text-slate-700">Audit-trail completeness</div><div className="text-2xl font-bold">{pct(r.results.audit?.complete_share)}</div><div className="text-xs">{r.results.audit?.complete_records}/{r.results.audit?.records_written} records</div></div>
            <div className="card"><div className="text-xs text-slate-700">Hash chain intact</div><div className="text-2xl font-bold">{r.results.audit?.chain_ok === undefined ? 'n/a' : r.results.audit.chain_ok ? 'Yes' : 'No'}</div></div>
          </div>

          <section className="card mb-4" aria-labelledby="ch">
            <h2 id="ch" className="mb-2 font-semibold">Guard off vs on (percent)</h2>
            <div className="h-72" role="img" aria-label="Grouped bar chart comparing metrics with the guard off and on">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="metric" tick={{ fontSize: 11 }} /><YAxis unit="%" /><Tooltip /><Legend />
                  <Bar dataKey="Guard off" fill="#dc2626" /><Bar dataKey="Guard on" fill="#13315c" /></BarChart>
              </ResponsiveContainer>
            </div>
            {na.length > 0 && <p className="mt-2 text-sm">n/a (not applicable for this dataset): {na.join(', ')}</p>}
            <Table caption="Overall metrics as a table">
              <thead><tr><Th>Metric</Th><Th>Guard off</Th><Th>Guard on</Th></tr></thead>
              <tbody>{METRICS.map(([k, l]) => <tr key={k}><th scope="row" className="td text-left">{l}</th><td className="td">{pct(o[`${k}_off`])}</td><td className="td">{pct(o[`${k}_on`])}</td></tr>)}</tbody>
            </Table>
          </section>

          <section className="mb-4" aria-labelledby="uc"><h2 id="uc" className="mb-2 font-semibold">Per use case</h2>
            <UseCaseTable rows={Object.entries(r.results.per_use_case || {}) as [string, M][]} /></section>

          <section className="mb-4" aria-labelledby="pr"><h2 id="pr" className="mb-2 font-semibold">Per rule</h2>
            <Table caption="Per rule results">
              <thead><tr><Th>Rule</Th><Th>Expected</Th><Th>Caught</Th><Th>Recall</Th><Th>Unexpected fires</Th></tr></thead>
              <tbody className="divide-y divide-slate-200">{(r.results.per_rule || []).map((x: M) => <tr key={x.rule_id}><th scope="row" className="td text-left font-mono text-xs">{x.rule_id}</th><td className="td">{x.expected}</td><td className="td">{x.caught}</td><td className="td">{pct(x.recall)}</td><td className="td">{x.unexpected_fires}</td></tr>)}</tbody>
            </Table></section>

          <section className="mb-4" aria-labelledby="mm"><h2 id="mm" className="mb-1 font-semibold">Misses and known gaps</h2>
            <p className="mb-2 text-sm text-slate-800">Items where the guard did not do what the label expects. These are honest misses or known gaps, not hidden.</p>
            {(r.results.mismatches || []).length === 0 ? <Empty>No mismatches in this run.</Empty> : (
              <Table caption="Mismatches between expected and actual action">
                <thead><tr><Th>Item</Th><Th>Use case</Th><Th>Input</Th><Th>Expected</Th><Th>Actual</Th><Th>Categories</Th><Th>Fired</Th></tr></thead>
                <tbody className="divide-y divide-slate-200">{r.results.mismatches.map((m: M) => (
                  <tr key={m.id}><td className="td font-mono text-xs">{m.id}</td><td className="td">{m.use_case}</td><td className="td max-w-xs break-words">{m.input}</td>
                    <td className="td"><ActionChip action={m.expected_action} /></td><td className="td"><ActionChip action={m.actual_action} /></td>
                    <td className="td">{(m.expected_categories || []).join(', ')}</td><td className="td">{(m.fired || []).join(', ') || 'none'}</td></tr>))}</tbody>
              </Table>)}</section>

          <section aria-labelledby="ib"><h2 id="ib" className="mb-2 font-semibold">Items browser</h2>
            <div className="mb-2 flex flex-wrap gap-3">
              <div><label htmlFor="fk" className="label">Kind</label><select id="fk" className="input" value={fKind} onChange={(e) => setFKind(e.target.value)}><option value="">All</option>{kinds.map((k) => <option key={k}>{k}</option>)}</select></div>
              <div><label htmlFor="fu" className="label">Use case</label><select id="fu" className="input" value={fUse} onChange={(e) => setFUse(e.target.value)}><option value="">All</option>{uses.map((k) => <option key={k}>{k}</option>)}</select></div>
            </div>
            <Status>{shown.length} of {items.length} items</Status>
            <Table caption="Evaluation items">
              <thead><tr><Th>Id</Th><Th>Use case</Th><Th>Kind</Th><Th>Input</Th><Th>Expected</Th><Th>Off</Th><Th>On</Th><Th>Fired</Th></tr></thead>
              <tbody className="divide-y divide-slate-200">{shown.slice(0, 200).map((i) => (
                <tr key={i.id}><td className="td font-mono text-xs">{i.id}</td><td className="td">{i.use_case}</td><td className="td">{i.kind}</td><td className="td max-w-xs break-words">{i.input}</td>
                  <td className="td"><ActionChip action={i.expected_action} /></td>
                  <td className="td"><ActionChip action={i.off_action} />{i.off_violation && <div className="text-xs text-red-800">violation</div>}</td>
                  <td className="td"><ActionChip action={i.on_action} />{i.on_violation && <div className="text-xs text-red-800">violation</div>}</td>
                  <td className="td">{(i.fired || []).join(', ')}</td></tr>))}</tbody>
            </Table>
            {shown.length > 200 && <p className="text-sm">Showing the first 200; narrow the filters to see more.</p>}
          </section>
        </>
      )}
    </div>
  )
}
