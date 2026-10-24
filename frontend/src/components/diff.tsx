import { useMemo } from 'react'

export interface Part { type: 'same' | 'del' | 'ins'; text: string }

export function wordDiff(a: string, b: string): Part[] {
  const ta = a.split(/(\s+)/).filter((x) => x !== '')
  const tb = b.split(/(\s+)/).filter((x) => x !== '')
  const n = ta.length
  const m = tb.length
  if (n * m > 4_000_000) return [{ type: 'del', text: a }, { type: 'ins', text: b }]
  const dp: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1))
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--) dp[i][j] = ta[i] === tb[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
  const out: Part[] = []
  const push = (type: Part['type'], text: string) => {
    const last = out[out.length - 1]
    if (last && last.type === type) last.text += text
    else out.push({ type, text })
  }
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (ta[i] === tb[j]) { push('same', ta[i]); i++; j++ }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { push('del', ta[i]); i++ }
    else { push('ins', tb[j]); j++ }
  }
  while (i < n) push('del', ta[i++])
  while (j < m) push('ins', tb[j++])
  return out
}

export function WordDiff({ before, after }: { before: string; after: string }) {
  const parts = useMemo(() => wordDiff(before || '', after || ''), [before, after])
  const changed = parts.some((p) => p.type !== 'same')
  return (
    <div>
      {!changed && <p className="mb-1 text-xs text-slate-700">No difference between raw and final output.</p>}
      <div className="whitespace-pre-wrap break-words rounded-md border border-slate-300 bg-white p-3 text-sm" data-testid="word-diff">
        {parts.map((p, i) =>
          p.type === 'same' ? <span key={i}>{p.text}</span>
          : p.type === 'del' ? <del key={i} className="bg-red-100 text-red-900 line-through"><span className="sr-only">[removed: </span>{p.text}<span className="sr-only">]</span></del>
          : <ins key={i} className="bg-green-100 text-green-900 no-underline"><span className="sr-only">[added: </span>{p.text}<span className="sr-only">]</span></ins>,
        )}
      </div>
    </div>
  )
}

const REDACT = /(\[[A-Z0-9_]*REDACT[A-Z0-9_]*\])/g
export function Redacted({ text }: { text: string }) {
  const parts = (text || '').split(REDACT)
  return (
    <div className="whitespace-pre-wrap break-words rounded-md border border-slate-300 bg-white p-3 text-sm">
      {parts.map((p, i) => (i % 2 === 1 ? <mark key={i} className="rounded bg-yellow-200 px-1 font-mono text-xs text-slate-900">{p}</mark> : <span key={i}>{p}</span>))}
    </div>
  )
}
