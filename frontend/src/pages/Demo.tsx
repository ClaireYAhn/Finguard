import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, errMsg } from '../api'
import { RuleTrace } from '../components/RuleTrace'
import { ActionChip, Callout, ErrorBox, PageHeader, Spinner, Status, Switch } from '../components/ui'
import { usePresentation } from '../context'
import type { DemoResult, DemoScenario, DemoSide, Scorecard } from '../types'

const LS_KEY = 'finguard.demo.last'
interface Stored { results: DemoResult[]; scorecard: Scorecard | null; provider?: string; model?: string }

function loadStored(): Stored | null {
  try { const s = localStorage.getItem(LS_KEY); return s ? (JSON.parse(s) as Stored) : null } catch { return null }
}
function saveStored(s: Stored) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(s)) } catch { /* storage unavailable */ }
}

function derive(results: DemoResult[]): Scorecard {
  const lat = results.map((r) => r.on.latency_ms - r.off.latency_ms).filter((x) => Number.isFinite(x))
  return {
    scenarios: results.length,
    harmful_off: results.filter((r) => r.off.harmful).length,
    harmful_on: results.filter((r) => r.on.harmful).length,
    stopped_or_fixed: results.filter((r) => r.off.harmful && !r.on.harmful).length,
    escalated_to_humans: results.filter((r) => r.on.action === 'escalate').length,
    avg_added_latency_ms: lat.length ? lat.reduce((a, b) => a + b, 0) / lat.length : 0,
  }
}

function Side({ title, side, note, withTrace, big }: { title: string; side?: DemoSide; note: string; withTrace?: boolean; big: boolean }) {
  return (
    <section className={`card ${withTrace ? 'border-navy-800' : 'border-red-300'}`} aria-label={title}>
      <h3 className={`mb-2 font-bold ${withTrace ? 'text-navy-800' : 'text-red-900'}`}>{title}</h3>
      {!side ? <p className="text-sm text-slate-800">{note || 'Not run yet.'}</p> : (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <ActionChip action={side.action} />
            <span className={`chip ring-1 ${side.harmful ? 'bg-red-100 text-red-900 ring-red-700' : 'bg-green-100 text-green-900 ring-green-700'}`}>{side.harmful ? 'Harmful outcome' : 'Not harmful'}</span>
            <span className="text-xs text-slate-700">{side.engine} · {side.model_received}</span>
          </div>
          <div className={`whitespace-pre-wrap rounded border border-slate-300 bg-slate-50 p-2 ${big ? '' : 'text-sm'}`}>{side.text}</div>
          <div className={big ? '' : 'text-sm'}><span className="font-semibold">Rules fired: </span>{side.rules_fired.length ? side.rules_fired.map((r) => <span key={r} className="chip mr-1 bg-slate-100 font-mono ring-1 ring-slate-400">{r}</span>) : 'none'}</div>
          {withTrace && <details><summary className="cursor-pointer text-sm font-medium">Show trace ({side.trace.length} checks)</summary><div className="mt-2 text-base"><RuleTrace trace={side.trace} /></div></details>}
          <p className="text-xs text-slate-700">{note}</p>
        </div>
      )}
    </section>
  )
}

function Bars({ sc }: { sc: Scorecard }) {
  const max = Math.max(sc.scenarios, 1)
  const row = (label: string, v: number, color: string) => (
    <div className="mb-2"><div className="mb-1 flex justify-between text-sm"><span>{label}</span><strong>{v} of {sc.scenarios}</strong></div>
      <div className="h-4 rounded bg-slate-200" aria-hidden="true"><div className="h-4 rounded" style={{ width: `${(v / max) * 100}%`, background: color }} /></div></div>
  )
  return <div>{row('Harmful outcomes without FinGuard', sc.harmful_off, '#dc2626')}{row('Harmful outcomes with FinGuard', sc.harmful_on, '#13315c')}{row('Stopped or fixed by FinGuard', sc.stopped_or_fixed, '#16a34a')}{row('Escalated to humans', sc.escalated_to_humans, '#7c3aed')}</div>
}

export default function Demo({ offline = false }: { offline?: boolean }) {
  const { presentation, setPresentation } = usePresentation()
  const stored = useMemo(loadStored, [])
  const [scenarios, setScenarios] = useState<DemoScenario[]>([])
  const [results, setResults] = useState<Record<string, DemoResult>>(() => Object.fromEntries((stored?.results || []).map((r) => [r.scenario_id, r])))
  const [scorecard, setScorecard] = useState<Scorecard | null>(stored?.scorecard ?? null)
  const [meta, setMeta] = useState<{ provider?: string; model?: string }>({ provider: stored?.provider, model: stored?.model })
  const [useCache, setUseCache] = useState(offline)
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [idx, setIdx] = useState(0)
  const [loading, setLoading] = useState(!offline)
  const [restored, setRestored] = useState(!!stored && stored.results.length > 0)

  const list: { id: string; s?: DemoScenario; r?: DemoResult }[] = useMemo(() => {
    if (scenarios.length) return scenarios.map((s) => ({ id: s.scenario_id, s, r: results[s.scenario_id] }))
    return Object.values(results).map((r) => ({ id: r.scenario_id, r }))
  }, [scenarios, results])

  useEffect(() => {
    if (offline) return
    let alive = true
    api<DemoScenario[]>('/api/demo/scenarios').then((s) => alive && setScenarios(s)).catch((e) => alive && setErr(errMsg(e))).finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [offline])

  const absorb = useCallback((res: DemoResult[], sc: Scorecard | null, provider?: string, model?: string, replace = false) => {
    setResults((prev) => {
      const next = replace ? {} as Record<string, DemoResult> : { ...prev }
      res.forEach((r) => { next[r.scenario_id] = r })
      saveStored({ results: Object.values(next), scorecard: sc, provider: provider ?? meta.provider, model: model ?? meta.model })
      return next
    })
    setScorecard(sc)
    setMeta((m) => ({ provider: provider ?? m.provider, model: model ?? m.model }))
    setRestored(false)
  }, [meta.provider, meta.model])

  const loadCache = useCallback(async () => {
    try {
      const c = await api<{ results: DemoResult[]; scorecard: Scorecard | null; provider?: string }>('/api/demo/cache')
      if (c.results?.length) { absorb(c.results, c.scorecard, c.provider, undefined, true); setMsg('Loaded cached results from the server.') }
      else setMsg('The server has no cached demo results yet. Run the scenarios first.')
    } catch (e) {
      setMsg(`${errMsg(e)} Using results saved in this browser${stored ? '.' : ' (none saved yet).'}`)
    }
  }, [absorb, stored])

  const toggleCache = (v: boolean) => { setUseCache(v); if (v) void loadCache() }

  const run = useCallback(async (id?: string) => {
    const key = id || 'all'
    setBusy(key); setErr(null); setMsg(null)
    try {
      if (id) {
        const r = await api<any>(`/api/demo/run/${encodeURIComponent(id)}`, { method: 'POST' })
        const arr: DemoResult[] = r.results ? r.results : [r]
        absorb(arr, null, r.provider, r.model)
        setMsg('Scenario finished.')
      } else {
        const r = await api<{ results: DemoResult[]; scorecard: Scorecard; provider: string; model: string }>('/api/demo/run-all', { method: 'POST' })
        absorb(r.results, r.scorecard, r.provider, r.model, true)
        setMsg('All scenarios finished.')
      }
    } catch (e) { setErr(errMsg(e)) } finally { setBusy(null) }
  }, [absorb])

  const exportJson = () => {
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), ...meta, scorecard: sc, results: Object.values(results) }, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob); a.download = 'finguard-demo-results.json'; a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 1000)
  }

  const resultList = Object.values(results)
  const sc = scorecard && scorecard.scenarios === resultList.length ? scorecard : resultList.length ? derive(resultList) : null
  const cur = list[Math.min(idx, Math.max(list.length - 1, 0))]

  const handlers = useRef({ run, setPresentation, presentation, list, idx, offline })
  handlers.current = { run, setPresentation, presentation, list, idx, offline }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const h = handlers.current
      const n = h.list.length
      if (e.key === 'ArrowRight' && n) setIdx((i) => Math.min(i + 1, n - 1))
      else if (e.key === 'ArrowLeft' && n) setIdx((i) => Math.max(i - 1, 0))
      else if ((e.key === 'r' || e.key === 'R') && !h.offline) { const c = h.list[Math.min(h.idx, n - 1)]; if (c) void h.run(c.id) }
      else if ((e.key === 'a' || e.key === 'A') && !h.offline) void h.run()
      else if (e.key === 'p' || e.key === 'P') h.setPresentation(!h.presentation)
      else if (e.key === 'Escape' && h.presentation) h.setPresentation(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const big = presentation
  const card = (c: (typeof list)[number]) => (
    <article key={c.id} className="mb-6" aria-labelledby={`sc-${c.id}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2 id={`sc-${c.id}`} className={`font-bold text-navy-900 ${big ? 'text-3xl' : 'text-lg'}`}>{c.s?.title ?? c.r?.title}</h2>
        <span className="chip bg-slate-100 ring-1 ring-slate-400">{c.s?.surface ?? c.r?.surface}</span>
        <span className="chip bg-slate-100 ring-1 ring-slate-400">{c.s?.use_case ?? c.r?.use_case}</span>
        {!offline && <button type="button" className="btn-primary" disabled={busy !== null} onClick={() => void run(c.id)}>{busy === c.id ? 'Running…' : 'Run'}<span className="sr-only"> {c.s?.title ?? c.r?.title}</span></button>}
      </div>
      <div className="mb-2 rounded border border-slate-300 bg-white p-2"><span className="font-semibold">Input: </span>{c.r?.input ?? c.s?.input}</div>
      <div className="grid gap-3 md:grid-cols-2">
        <Side title="Without FinGuard" side={c.r?.off} note={c.r?.without_note ?? c.s?.without ?? ''} big={big} />
        <Side title="With FinGuard" side={c.r?.on} note={c.r?.with_note ?? c.s?.with ?? ''} withTrace big={big} />
      </div>
    </article>
  )

  return (
    <div className={big ? 'text-2xl leading-relaxed' : ''}>
      <PageHeader title="Demo">
        <label className="flex items-center gap-2 text-sm font-medium"><Switch checked={useCache} onChange={toggleCache} label="Use cached results (works offline)" /> Use cached results (works offline)</label>
        {!offline && <button type="button" className="btn-primary" disabled={busy !== null} onClick={() => void run()}>{busy === 'all' ? 'Running…' : 'Run all'}</button>}
        <button type="button" className="btn-secondary" disabled={!resultList.length} onClick={exportJson}>Export JSON</button>
        <button type="button" className="btn-secondary" aria-pressed={presentation} onClick={() => setPresentation(!presentation)}>{presentation ? 'Exit presentation (Esc)' : 'Presentation mode (P)'}</button>
      </PageHeader>

      <p className="mb-2 text-sm text-slate-800" id="shortcuts">
        Keyboard shortcuts: <kbd className="rounded border px-1">←</kbd>/<kbd className="rounded border px-1">→</kbd> previous/next scenario, <kbd className="rounded border px-1">R</kbd> run current, <kbd className="rounded border px-1">A</kbd> run all, <kbd className="rounded border px-1">P</kbd> toggle presentation, <kbd className="rounded border px-1">Esc</kbd> exit presentation.
      </p>
      {meta.model && <p className="mb-2 text-sm">Outputs produced by provider <strong>{meta.provider}</strong>, model <strong>{meta.model}</strong>.{(meta.provider || '').toLowerCase().includes('mock') && ' The mock provider deliberately produces risky answers when no API key is configured.'}</p>}
      {restored && <div className="mb-2"><Callout tone="warn">Showing results saved earlier in this browser. Run again for fresh results.</Callout></div>}
      <div aria-live="polite">{busy && <Spinner label="Running…" />}<Status>{msg}</Status></div>
      {err && <ErrorBox message={err} />}
      {loading && <Spinner />}

      {sc && (
        <section className="card mb-4" aria-labelledby="score">
          <h2 id="score" className="mb-1 font-semibold">Risk scorecard</h2>
          <p className="mb-3 font-medium" role="status">
            {sc.harmful_off} of {sc.scenarios} scenarios produced a harmful outcome without FinGuard; {sc.harmful_on} with FinGuard; {sc.escalated_to_humans} escalated to humans.
            {Number.isFinite(sc.avg_added_latency_ms) && ` Average added latency ${Number(sc.avg_added_latency_ms).toFixed(1)} ms.`}
          </p>
          <Bars sc={sc} />
        </section>
      )}

      {!loading && list.length === 0 && !err && <div className="card">No scenarios available.</div>}
      {presentation ? (
        <>
          {cur && card(cur)}
          {list.length > 0 && (
            <div className="flex items-center gap-3">
              <button type="button" className="btn-secondary" onClick={() => setIdx(Math.max(0, idx - 1))} disabled={idx === 0}>Previous</button>
              <span>Scenario {Math.min(idx, list.length - 1) + 1} of {list.length}</span>
              <button type="button" className="btn-secondary" onClick={() => setIdx(Math.min(list.length - 1, idx + 1))} disabled={idx >= list.length - 1}>Next</button>
            </div>
          )}
        </>
      ) : list.map(card)}
    </div>
  )
}
