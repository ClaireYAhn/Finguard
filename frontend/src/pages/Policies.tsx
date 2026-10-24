import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, errMsg } from '../api'
import { Callout, ConfirmDialog, Empty, ErrorBox, PageHeader, Spinner, Status, Switch } from '../components/ui'
import { fmtTime, useFetch } from '../hooks'
import type { PolicyPack, PolicyRule } from '../types'

interface PackSummary { pack: string; title: string; version: number; risk_tier: string; rules_enabled: number; rules_total: number }
interface Hist { version: number; created_at: string; author: string; note: string }
interface DiffRes { pack: string; from: number; to: number; unified: string; changes: { rule_id: string; fields: string[]; before: any; after: any }[] }

const STAGES = ['input', 'dialogue', 'retrieval', 'output', 'tool']
const ACTIONS = ['allow', 'modify', 'block', 'escalate', 'log']

function JsonArea({ id, label, value, onValid, rows = 3 }: { id: string; label: string; value: unknown; onValid: (v: any) => void; rows?: number }) {
  const [text, setText] = useState(JSON.stringify(value, null, 2))
  const [err, setErr] = useState<string | null>(null)
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <textarea id={id} className="input font-mono" rows={rows} value={text} aria-invalid={!!err} aria-describedby={err ? `${id}-e` : undefined}
        onChange={(e) => { setText(e.target.value); try { onValid(JSON.parse(e.target.value)); setErr(null) } catch { setErr('Invalid JSON: changes are not applied until this is valid.') } }} />
      {err && <p id={`${id}-e`} role="alert" className="text-xs text-red-800">{err}</p>}
    </div>
  )
}

function RuleCard({ r, onChange }: { r: PolicyRule; onChange: (p: Partial<PolicyRule>) => void }) {
  return (
    <div className="rounded-md border border-slate-300 bg-white p-3 text-slate-900">
      <div className="flex flex-wrap items-center gap-3">
        <Switch checked={r.enabled} onChange={(v) => onChange({ enabled: v })} label={`Enable rule ${r.id}`} />
        <div className="min-w-0 flex-1"><div className="font-medium">{r.name} <span className="font-mono text-xs text-slate-700">{r.id}</span></div><div className="text-sm text-slate-800">{r.description}</div></div>
        <div><label htmlFor={`sev-${r.id}`} className="sr-only">Severity for {r.id}</label>
          <select id={`sev-${r.id}`} className="input w-auto" value={r.severity} onChange={(e) => onChange({ severity: e.target.value })}>{['low', 'medium', 'high'].map((s) => <option key={s}>{s}</option>)}</select></div>
        <div><label htmlFor={`act-${r.id}`} className="sr-only">Action for {r.id}</label>
          <select id={`act-${r.id}`} className="input w-auto" value={r.action} onChange={(e) => onChange({ action: e.target.value })}>{ACTIONS.map((s) => <option key={s}>{s}</option>)}</select></div>
      </div>
      {Object.keys(r.thresholds || {}).length > 0 && <div className="mt-2"><JsonArea id={`th-${r.id}`} label="Thresholds (JSON)" value={r.thresholds} onValid={(v) => onChange({ thresholds: v })} /></div>}
      {r.regulations?.length > 0 && (
        <details className="mt-2 text-sm"><summary className="cursor-pointer">Regulation references ({r.regulations.length}) <span className="text-xs text-slate-700">illustrative, not legal advice</span></summary>
          <ul className="list-disc pl-5">{r.regulations.map((g, i) => <li key={i}><strong>{g.ref}</strong>: {g.why}</li>)}</ul></details>
      )}
    </div>
  )
}

function DiffView({ d }: { d: DiffRes }) {
  return (
    <div>
      <h4 className="mb-1 font-medium">Changes v{d.from} to v{d.to}</h4>
      {d.changes.length === 0 ? <p className="text-sm">No rule-level changes.</p> : (
        <ul className="mb-2 list-disc pl-5 text-sm">{d.changes.map((c, i) => <li key={i}><span className="font-mono">{c.rule_id}</span>: {c.fields.join(', ')}</li>)}</ul>
      )}
      <pre className="code" tabIndex={0} aria-label="Unified diff">
        {(d.unified || '(no textual differences)').split('\n').map((l, i) => (
          <div key={i} className={l.startsWith('+') && !l.startsWith('+++') ? 'bg-green-900/60 text-green-100' : l.startsWith('-') && !l.startsWith('---') ? 'bg-red-900/60 text-red-100' : l.startsWith('@@') ? 'text-sky-300' : ''}>{l || ' '}</div>
        ))}
      </pre>
    </div>
  )
}

export default function Policies() {
  const [sp, setSp] = useSearchParams()
  const list = useFetch<PackSummary[]>('packs', () => api('/api/policies'))
  const pack = sp.get('pack') || list.data?.[0]?.pack || ''
  const cur = useFetch<PolicyPack | null>(`pack-${pack}`, () => (pack ? api(`/api/policies/${pack}`) : Promise.resolve(null)))
  const hist = useFetch<Hist[] | null>(`hist-${pack}`, () => (pack ? api(`/api/policies/${pack}/history`) : Promise.resolve(null)))
  const [draft, setDraft] = useState<PolicyPack | null>(null)
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [from, setFrom] = useState<number | ''>('')
  const [to, setTo] = useState<number | ''>('')
  const [diff, setDiff] = useState<DiffRes | null>(null)
  const [diffErr, setDiffErr] = useState<string | null>(null)
  const [rb, setRb] = useState<number | null>(null)
  const [settingsOk, setSettingsOk] = useState(true)

  useEffect(() => { if (cur.data) setDraft(JSON.parse(JSON.stringify(cur.data))) }, [cur.data])
  useEffect(() => { setDiff(null); setFrom(''); setTo('') }, [pack])

  const upd = (id: string, p: Partial<PolicyRule>) => setDraft((d) => d && { ...d, rules: d.rules.map((r) => (r.id === id ? { ...r, ...p } : r)) })
  const save = async () => {
    if (!draft) return
    setBusy(true); setMsg(null)
    try {
      const r = await api(`/api/policies/${pack}`, { method: 'PUT', body: { pack: draft, note } })
      setMsg(`Saved as version ${r.version ?? ''}.`); setNote(''); cur.reload(); hist.reload(); list.reload()
    } catch (e) { setMsg(errMsg(e)) } finally { setBusy(false) }
  }
  const showDiff = async () => {
    if (from === '' || to === '') return
    setDiffErr(null)
    try { setDiff(await api(`/api/policies/${pack}/diff?from=${from}&to=${to}`)) } catch (e) { setDiff(null); setDiffErr(errMsg(e)) }
  }
  const rollback = async () => {
    if (rb === null) return
    try { await api(`/api/policies/${pack}/rollback`, { method: 'POST', body: { version: rb } }); setMsg(`Rolled back to version ${rb} (saved as a new version).`); cur.reload(); hist.reload() }
    catch (e) { setMsg(errMsg(e)) }
    setRb(null)
  }

  return (
    <div>
      <PageHeader title="Policies">
        <label htmlFor="pack" className="text-sm font-medium">Policy pack</label>
        <select id="pack" className="input w-auto" value={pack} onChange={(e) => setSp({ pack: e.target.value })}>
          {list.data?.map((p) => <option key={p.pack} value={p.pack}>{p.title} (v{p.version}, {p.rules_enabled}/{p.rules_total} rules on)</option>)}
        </select>
      </PageHeader>
      <div className="mb-3"><Callout>Regulation mappings are <strong>illustrative, not legal advice</strong>. Editing creates a new version; older versions stay in history.</Callout></div>
      {(list.error || cur.error) && <ErrorBox message={list.error || cur.error || ''} onRetry={() => { list.reload(); cur.reload() }} />}
      {(list.loading || cur.loading) && <Spinner />}
      {list.data && list.data.length === 0 && <Empty>No policy packs found.</Empty>}
      {draft && (
        <>
          <p className="mb-3 text-sm">Editing <strong>{draft.title}</strong> version {cur.data?.version}, risk tier {draft.risk_tier}. {draft.regulation_note}</p>
          {STAGES.concat([...new Set(draft.rules.map((r) => r.stage))].filter((s) => !STAGES.includes(s))).map((stage) => {
            const rules = draft.rules.filter((r) => r.stage === stage)
            if (!rules.length) return null
            return (
              <section key={stage} className="mb-4" aria-labelledby={`st-${stage}`}>
                <h2 id={`st-${stage}`} className="mb-2 text-lg font-semibold capitalize text-navy-900">{stage} rules</h2>
                <div className="space-y-2">{rules.map((r) => <RuleCard key={r.id} r={r} onChange={(p) => upd(r.id, p)} />)}</div>
              </section>
            )
          })}
          <section className="card mb-4"><h2 className="mb-2 font-semibold">Pack settings</h2>
            <JsonArea id="settings" label="Settings JSON (disclosures, blocked_topics, redirect_message, ...)" rows={10} value={draft.settings}
              onValid={(v) => { setSettingsOk(true); setDraft((d) => d && { ...d, settings: v }) }} />
            {!settingsOk && <p className="text-xs text-red-800">Settings invalid.</p>}
          </section>
          <section className="card mb-6"><h2 className="mb-2 font-semibold">Save as new version</h2>
            <label htmlFor="note" className="label">Change note</label>
            <input id="note" className="input mb-2" value={note} onChange={(e) => setNote(e.target.value)} />
            <button type="button" className="btn-primary" disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Save as new version'}</button>
            <Status>{msg}</Status>
          </section>
        </>
      )}
      {hist.data && (
        <section className="card" aria-labelledby="hist">
          <h2 id="hist" className="mb-2 font-semibold">Version history</h2>
          <ul className="mb-4 divide-y divide-slate-200">
            {hist.data.map((h) => (
              <li key={h.version} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                <strong>v{h.version}</strong><span>{fmtTime(h.created_at)}</span><span>by {h.author}</span><span className="text-slate-800">{h.note}</span>
                <button type="button" className="btn-secondary ml-auto" onClick={() => setRb(h.version)} aria-label={`Roll back to version ${h.version}`}>Roll back</button>
              </li>
            ))}
          </ul>
          <h3 className="mb-2 font-medium">Compare versions</h3>
          <div className="mb-3 flex flex-wrap items-end gap-2">
            {(['from', 'to'] as const).map((k) => (
              <div key={k}><label htmlFor={`d-${k}`} className="label">{k === 'from' ? 'From version' : 'To version'}</label>
                <select id={`d-${k}`} className="input w-auto" value={k === 'from' ? from : to} onChange={(e) => (k === 'from' ? setFrom : setTo)(e.target.value === '' ? '' : Number(e.target.value))}>
                  <option value="">Select</option>{hist.data?.map((h) => <option key={h.version} value={h.version}>v{h.version}</option>)}</select></div>
            ))}
            <button type="button" className="btn-secondary" disabled={from === '' || to === ''} onClick={() => void showDiff()}>Show diff</button>
          </div>
          {diffErr && <ErrorBox message={diffErr} />}
          {diff && <DiffView d={diff} />}
        </section>
      )}
      {rb !== null && <ConfirmDialog title="Roll back policy" confirmLabel="Roll back" message={<>Roll back <strong>{pack}</strong> to version {rb}? This creates a new version with that content and takes effect immediately.</>} onConfirm={() => void rollback()} onCancel={() => setRb(null)} />}
    </div>
  )
}
