import { useState } from 'react'
import type { CheckResult } from '../types'
import { ActionChip, SeverityChip } from './ui'

export function RuleTrace({ trace, defaultOpen = false }: { trace: CheckResult[]; defaultOpen?: boolean }) {
  if (!trace || trace.length === 0) return <p className="text-sm text-slate-800">No rules were evaluated for this record.</p>
  return (
    <ol className="space-y-2" aria-label="Rule trace">
      {trace.map((r, i) => (
        <TraceItem key={`${r.rule_id}-${i}`} r={r} defaultOpen={defaultOpen || r.status !== 'pass'} />
      ))}
    </ol>
  )
}

function TraceItem({ r, defaultOpen }: { r: CheckResult; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <li className="rounded-md border border-slate-300 bg-white text-slate-900">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full flex-wrap items-center gap-2 px-3 py-2 text-left"
      >
        <span aria-hidden="true">{open ? '▾' : '▸'}</span>
        <span className="font-mono text-xs">{r.rule_id}</span>
        <span className="text-sm font-medium">{r.name}</span>
        <ActionChip action={r.status} />
        <SeverityChip severity={r.severity} />
        <span className="ml-auto text-xs text-slate-700">{r.stage} · {r.check_type} · {Number(r.latency_ms).toFixed(2)} ms</span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-slate-200 px-3 py-2 text-sm">
          <p>{r.explanation || 'No explanation recorded.'}</p>
          {r.error && <p className="text-red-800">Check error: {r.error}</p>}
          {r.evidence?.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase text-slate-700">Evidence</div>
              <ul className="list-disc pl-5">
                {r.evidence.map((e, i) => <li key={i} className="break-words font-mono text-xs">{e}</li>)}
              </ul>
            </div>
          )}
          {r.regulations?.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase text-slate-700">
                Regulation references <span className="ml-1 normal-case font-normal">(illustrative, not legal advice)</span>
              </div>
              <ul className="list-disc pl-5">
                {r.regulations.map((g, i) => <li key={i}><strong>{g.ref}</strong>: {g.why}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  )
}
