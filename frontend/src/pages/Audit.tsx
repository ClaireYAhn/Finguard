import { useState } from 'react'
import { api, qs } from '../api'
import { AuditDetailDrawer } from '../components/AuditDetail'
import { Callout, Empty, ErrorBox, PageHeader, Spinner, Status } from '../components/ui'
import { useFetch } from '../hooks'
import type { App, AuditRecord } from '../types'
import { AuditRows } from './Live'

interface Verify { ok: boolean; count: number; head_hash: string; broken_at: number | null; audit_id: string | null; message: string }
const PAGE = 50
const EMPTY = { app_id: '', action: '', rule: '', severity: '', channel: '', from: '', to: '', q: '' }

export default function Audit() {
  const [draft, setDraft] = useState(EMPTY)
  const [filters, setFilters] = useState(EMPTY)
  const [offset, setOffset] = useState(0)
  const [sel, setSel] = useState<AuditRecord | null>(null)
  const [ver, setVer] = useState<Verify | null>(null)
  const [verErr, setVerErr] = useState<string | null>(null)
  const [verBusy, setVerBusy] = useState(false)
  const apps = useFetch<App[]>('audit-apps', () => api('/api/apps'))
  const query = qs({ ...filters, limit: PAGE, offset })
  const q = useFetch<AuditRecord[]>(`audit-${query}`, () => api(`/api/audit${query}`))
  const exportQs = (f: 'csv' | 'json') => `/api/audit/export${qs({ ...filters, format: f })}`
  const set = (k: string, v: string) => setDraft((p) => ({ ...p, [k]: v }))

  const verify = async () => {
    setVerBusy(true); setVerErr(null)
    try { setVer(await api<Verify>('/api/audit/verify')) } catch (e) { setVerErr(e instanceof Error ? e.message : String(e)) } finally { setVerBusy(false) }
  }
  const sel_ = (id: string, label: string, opts: string[], extra?: [string, string][]) => (
    <div><label htmlFor={id} className="label">{label}</label>
      <select id={id} className="input" value={(draft as any)[id]} onChange={(e) => set(id, e.target.value)}>
        <option value="">All</option>{extra?.map(([v, l]) => <option key={v} value={v}>{l}</option>)}{opts.map((o) => <option key={o}>{o}</option>)}
      </select></div>
  )

  return (
    <div>
      <PageHeader title="Audit">
        <button type="button" className="btn-primary" disabled={verBusy} onClick={() => void verify()}>{verBusy ? 'Verifying…' : 'Verify chain'}</button>
        <a className="btn-secondary" href={exportQs('csv')}>Export CSV</a>
        <a className="btn-secondary" href={exportQs('json')}>Export JSON</a>
      </PageHeader>
      <div className="mb-3" aria-live="polite">
        {verErr && <ErrorBox message={verErr} />}
        {ver && <Callout tone={ver.ok ? 'info' : 'warn'}>
          <strong>{ver.ok ? 'Chain verified.' : 'Chain broken.'}</strong> {ver.message} ({ver.count} records){ver.broken_at !== null && ver.broken_at !== undefined && <> Broken at index {ver.broken_at}{ver.audit_id ? ` (record ${ver.audit_id})` : ''}.</>}
          <div className="break-all font-mono text-xs">head hash: {ver.head_hash || 'n/a'}</div>
        </Callout>}
        <p className="mt-2 text-xs text-slate-800">This demonstrates tamper evidence and is not a certified immutable store. Removing the newest records is only detectable if the head hash is stored elsewhere.</p>
      </div>
      <form className="card mb-4 grid grid-cols-2 gap-3 md:grid-cols-4" onSubmit={(e) => { e.preventDefault(); setOffset(0); setFilters(draft) }}>
        <div><label htmlFor="app_id" className="label">App</label>
          <select id="app_id" className="input" value={draft.app_id} onChange={(e) => set('app_id', e.target.value)}><option value="">All</option>{apps.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
        {sel_('action', 'Action', ['allow', 'modify', 'block', 'escalate', 'error', 'review_approved', 'review_rejected'])}
        <div><label htmlFor="rule" className="label">Rule id</label><input id="rule" className="input" value={draft.rule} onChange={(e) => set('rule', e.target.value)} /></div>
        {sel_('severity', 'Severity', ['low', 'medium', 'high'])}
        {sel_('channel', 'Channel', ['gateway', 'tool-call', 'hook', 'demo', 'simulated', 'review'])}
        <div><label htmlFor="from" className="label">From date</label><input id="from" type="date" className="input" value={draft.from} onChange={(e) => set('from', e.target.value)} /></div>
        <div><label htmlFor="to" className="label">To date</label><input id="to" type="date" className="input" value={draft.to} onChange={(e) => set('to', e.target.value)} /></div>
        <div><label htmlFor="q" className="label">Text search</label><input id="q" className="input" value={draft.q} onChange={(e) => set('q', e.target.value)} /></div>
        <div className="col-span-2 flex gap-2 md:col-span-4">
          <button type="submit" className="btn-primary">Apply filters</button>
          <button type="button" className="btn-secondary" onClick={() => { setDraft(EMPTY); setFilters(EMPTY); setOffset(0) }}>Clear</button>
        </div>
      </form>
      {q.error && <ErrorBox message={q.error} onRetry={q.reload} />}
      {q.loading && <Spinner />}
      {q.data && q.data.length === 0 && <Empty>No audit records match these filters.</Empty>}
      {q.data && q.data.length > 0 && <AuditRows rows={q.data} onOpen={setSel} />}
      <div className="mt-3 flex items-center gap-3">
        <button type="button" className="btn-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
        <Status>Showing {q.data && q.data.length ? `${offset + 1}-${offset + q.data.length}` : '0'}</Status>
        <button type="button" className="btn-secondary" disabled={!q.data || q.data.length < PAGE} onClick={() => setOffset(offset + PAGE)}>Next</button>
      </div>
      {sel && <AuditDetailDrawer id={sel.id} preview={sel} onClose={() => setSel(null)} />}
    </div>
  )
}
