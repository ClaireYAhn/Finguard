import { useState } from 'react'
import { api, errMsg } from '../api'
import { Redacted } from '../components/diff'
import { Chip, Empty, ErrorBox, PageHeader, SeverityChip, Spinner, Status } from '../components/ui'
import { fmtTime, useFetch } from '../hooks'
import type { ReviewCase } from '../types'

function Payload({ p }: { p: Record<string, any> }) {
  if (p.tool) {
    return (
      <div className="space-y-1 text-sm">
        <div>Agent <strong>{p.agent_id}</strong> wants to call tool <code className="font-mono">{p.tool}</code> (user {p.user}, role {p.role})</div>
        <pre className="code" tabIndex={0}>{JSON.stringify(p.arguments, null, 2)}</pre>
      </div>
    )
  }
  return (
    <div className="space-y-2 text-sm">
      {p.input !== undefined && <div><div className="text-xs font-semibold text-slate-700">Input</div><Redacted text={String(p.input)} /></div>}
      {p.proposed_output !== undefined && <div><div className="text-xs font-semibold text-slate-700">Proposed output</div><Redacted text={String(p.proposed_output)} /></div>}
      {p.final_output !== undefined && <div><div className="text-xs font-semibold text-slate-700">Final output shown</div><Redacted text={String(p.final_output)} /></div>}
    </div>
  )
}

function CaseCard({ c, onDone }: { c: ReviewCase; onDone: () => void }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const decide = async (decision: 'approved' | 'rejected') => {
    setBusy(true); setMsg(null)
    try { await api(`/api/reviews/${c.id}/decide`, { method: 'POST', body: { decision, note } }); setMsg(`Case ${decision}.`); onDone() }
    catch (e) { setMsg(errMsg(e)); setBusy(false) }
  }
  return (
    <article className="card" aria-labelledby={`case-${c.id}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2 id={`case-${c.id}`} className="font-semibold">{c.kind} · {c.app_name}</h2>
        <SeverityChip severity={c.severity} /><Chip>{c.status}</Chip>
        <span className="text-xs text-slate-700">{fmtTime(c.created_at)}</span>
      </div>
      <p className="mb-2 text-sm">{c.reason}</p>
      <div className="mb-2 flex flex-wrap gap-1">{c.rule_ids.map((r) => <span key={r} className="chip bg-slate-100 font-mono ring-1 ring-slate-400">{r}</span>)}</div>
      <Payload p={c.payload} />
      {c.status === 'open' ? (
        <div className="mt-3">
          <label htmlFor={`n-${c.id}`} className="label">Reviewer note</label>
          <textarea id={`n-${c.id}`} className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="mt-2 flex gap-2">
            <button type="button" className="btn-primary" disabled={busy} onClick={() => void decide('approved')}>Approve</button>
            <button type="button" className="btn-danger" disabled={busy} onClick={() => void decide('rejected')}>Reject</button>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-sm">Decided {fmtTime(c.decided_at)}. Note: {c.reviewer_note || '(none)'}</p>
      )}
      <Status>{msg}</Status>
    </article>
  )
}

export default function Reviews() {
  const [tab, setTab] = useState<'open' | 'approved' | 'rejected'>('open')
  const q = useFetch<ReviewCase[]>(`rev-${tab}`, () => api(`/api/reviews?status=${tab}`), { interval: 10000 })
  return (
    <div>
      <PageHeader title="Review queue" />
      <div role="tablist" aria-label="Review status" className="mb-3 flex gap-1">
        {(['open', 'approved', 'rejected'] as const).map((t) => (
          <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`btn ${tab === t ? 'border-navy-800 bg-navy-800 text-white' : 'border-slate-400 bg-white text-slate-900'}`}>
            {t[0].toUpperCase() + t.slice(1)}{tab === t && q.data ? ` (${q.data.length})` : ''}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {q.error && <ErrorBox message={q.error} onRetry={q.reload} />}
        {q.loading && <Spinner />}
        {q.data && q.data.length === 0 && <Empty>No {tab} cases.</Empty>}
        <div className="space-y-3">{q.data?.map((c) => <CaseCard key={c.id} c={c} onDone={q.reload} />)}</div>
      </div>
    </div>
  )
}
