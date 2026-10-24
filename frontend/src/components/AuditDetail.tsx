import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtTime } from '../hooks'
import type { AuditRecord } from '../types'
import { Redacted, WordDiff } from './diff'
import { RuleTrace } from './RuleTrace'
import { ActionChip, ChannelBadge, Dialog, ErrorBox, Spinner } from './ui'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-5">
      <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-navy-800">{title}</h3>
      {children}
    </section>
  )
}
function Plain({ text }: { text: string }) {
  return <div className="whitespace-pre-wrap break-words rounded-md border border-slate-300 bg-white p-3 text-sm">{text || <em className="text-slate-700">(empty)</em>}</div>
}

export function AuditDetailDrawer({ id, preview, onClose }: { id: string; preview?: AuditRecord; onClose: () => void }) {
  const [rec, setRec] = useState<AuditRecord | null>(preview || null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    api<AuditRecord>(`/api/audit/${encodeURIComponent(id)}`).then((r) => alive && setRec(r)).catch((e) => alive && setErr(e.message))
    return () => { alive = false }
  }, [id])

  return (
    <Dialog side wide title={`Audit record ${id}`} onClose={onClose}>
      {err && <ErrorBox message={err} />}
      {!rec && !err && <Spinner />}
      {rec && (
        <div>
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
            <ActionChip action={rec.final_action} />
            <ChannelBadge channel={rec.channel} />
            <span>{rec.app_name}</span>
            <span className="text-slate-700">{fmtTime(rec.ts)}</span>
            <span className="text-slate-700">user {rec.user} · role {rec.role}</span>
          </div>
          <Section title="Input">
            <div className="grid gap-3 md:grid-cols-2">
              <div><div className="mb-1 text-xs font-semibold text-slate-700">Original input</div>
                {rec.original_input ? <Plain text={rec.original_input} /> : <p className="text-sm text-slate-800">Not stored (raw storage is off).</p>}</div>
              <div><div className="mb-1 text-xs font-semibold text-slate-700">Redacted input (as sent onward)</div><Redacted text={rec.redacted_input} /></div>
            </div>
          </Section>
          <Section title="Output">
            <div className="grid gap-3 md:grid-cols-2">
              <div><div className="mb-1 text-xs font-semibold text-slate-700">Raw model output</div>
                {rec.raw_output ? <Plain text={rec.raw_output} /> : <p className="text-sm text-slate-800">Not stored.</p>}</div>
              <div><div className="mb-1 text-xs font-semibold text-slate-700">Final output</div><Plain text={rec.final_output} /></div>
            </div>
            <div className="mt-3">
              <div className="mb-1 text-xs font-semibold text-slate-700">
                Word diff, raw to final (<del className="bg-red-100 text-red-900">removed</del> / <ins className="bg-green-100 text-green-900 no-underline">added</ins>)
              </div>
              <WordDiff before={rec.raw_output} after={rec.final_output} />
            </div>
          </Section>
          <Section title="Rule trace">
            <p className="mb-2 text-xs text-slate-700">Regulation mappings are illustrative, not legal advice.</p>
            <RuleTrace trace={rec.rule_results} />
          </Section>
          <Section title="Latency, engine and provenance">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm md:grid-cols-3">
              {Object.entries(rec.latency || {}).map(([k, v]) => (<div key={k}><dt className="text-xs text-slate-700">{k}</dt><dd>{Number(v).toFixed(1)} ms</dd></div>))}
              <div><dt className="text-xs text-slate-700">engine</dt><dd>{rec.engine}</dd></div>
              <div><dt className="text-xs text-slate-700">policy pack</dt><dd>{rec.pack}@{rec.pack_version}</dd></div>
              <div><dt className="text-xs text-slate-700">model</dt><dd>{rec.model || 'n/a'}</dd></div>
            </dl>
            <dl className="mt-2 space-y-1 text-xs">
              <div><dt className="inline font-semibold">prev_hash: </dt><dd className="inline break-all font-mono">{rec.prev_hash}</dd></div>
              <div><dt className="inline font-semibold">hash: </dt><dd className="inline break-all font-mono">{rec.hash}</dd></div>
            </dl>
            {rec.extra && Object.keys(rec.extra).length > 0 && <pre className="code mt-2" tabIndex={0}>{JSON.stringify(rec.extra, null, 2)}</pre>}
          </Section>
        </div>
      )}
    </Dialog>
  )
}
