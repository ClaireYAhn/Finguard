import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

export const ACTION_COLORS: Record<string, string> = {
  allow: '#16a34a',
  modify: '#d97706',
  block: '#dc2626',
  escalate: '#7c3aed',
}

const ACTION_CLASS: Record<string, string> = {
  allow: 'bg-green-100 text-green-900 ring-1 ring-green-700',
  pass: 'bg-green-100 text-green-900 ring-1 ring-green-700',
  modify: 'bg-amber-100 text-amber-900 ring-1 ring-amber-700',
  modified: 'bg-amber-100 text-amber-900 ring-1 ring-amber-700',
  block: 'bg-red-100 text-red-900 ring-1 ring-red-700',
  blocked: 'bg-red-100 text-red-900 ring-1 ring-red-700',
  escalate: 'bg-purple-100 text-purple-900 ring-1 ring-purple-700',
  escalated: 'bg-purple-100 text-purple-900 ring-1 ring-purple-700',
  review_approved: 'bg-green-100 text-green-900 ring-1 ring-green-700',
  review_rejected: 'bg-red-100 text-red-900 ring-1 ring-red-700',
  error: 'bg-slate-200 text-slate-900 ring-1 ring-slate-600',
  log: 'bg-slate-100 text-slate-900 ring-1 ring-slate-500',
}
const ACTION_ICON: Record<string, string> = {
  allow: '✓', pass: '✓', modify: '✎', modified: '✎', block: '⛔', blocked: '⛔', escalate: '⚑', escalated: '⚑', error: '!',
}

export function ActionChip({ action }: { action: string }) {
  return (
    <span className={`chip ${ACTION_CLASS[action] || 'bg-slate-100 text-slate-900 ring-1 ring-slate-500'}`}>
      <span aria-hidden="true" className="mr-1">{ACTION_ICON[action] || ''}</span>
      {action.replace('_', ' ')}
    </span>
  )
}

const TIER_CLASS: Record<string, string> = {
  minimal: 'bg-sky-100 text-sky-900 ring-1 ring-sky-700',
  limited: 'bg-amber-100 text-amber-900 ring-1 ring-amber-700',
  high: 'bg-red-100 text-red-900 ring-1 ring-red-700',
}
export function TierChip({ tier }: { tier: string }) {
  return <span className={`chip ${TIER_CLASS[tier] || 'bg-slate-100 text-slate-900'}`}>{tier} risk</span>
}

export function SeverityChip({ severity }: { severity: string }) {
  const c = severity === 'high' ? 'bg-red-100 text-red-900' : severity === 'medium' ? 'bg-amber-100 text-amber-900' : 'bg-slate-100 text-slate-900'
  return <span className={`chip ${c}`}>{severity}</span>
}

export function Chip({ children, className = 'bg-slate-100 text-slate-900 ring-1 ring-slate-400' }: { children: ReactNode; className?: string }) {
  return <span className={`chip ${className}`}>{children}</span>
}

export function ChannelBadge({ channel }: { channel: string }) {
  if (channel === 'simulated') return <SimBadge />
  return <span className="chip bg-slate-100 text-slate-900 ring-1 ring-slate-400">{channel}</span>
}

export function SimBadge({ label = 'Simulated traffic' }: { label?: string }) {
  return <span className="chip bg-orange-100 text-orange-950 ring-1 ring-orange-700 whitespace-nowrap">{label}</span>
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 p-4 text-sm text-slate-800">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-navy-800 border-t-transparent" aria-hidden="true" />
      {label}
    </div>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-md border border-red-700 bg-red-50 p-3 text-sm text-red-950">
      <strong>Something went wrong.</strong> {message}
      {onRetry && (
        <button type="button" className="btn-secondary ml-3" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-md border border-dashed border-slate-400 bg-white p-6 text-center text-sm text-slate-800">{children}</div>
}

export function Callout({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' }) {
  const c = tone === 'warn' ? 'border-amber-700 bg-amber-50 text-amber-950' : 'border-navy-700 bg-navy-50 text-navy-900'
  return <div className={`rounded-md border-l-4 p-3 text-sm ${c}`}>{children}</div>
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h1 className="text-2xl font-bold text-navy-900">{title}</h1>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

export function Status({ children }: { children: ReactNode }) {
  return (
    <div aria-live="polite" role="status" className="text-sm text-slate-800">
      {children}
    </div>
  )
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-slate-600 disabled:opacity-50 ${checked ? 'bg-green-700' : 'bg-slate-300'}`}
    >
      <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition ${checked ? 'translate-x-6' : 'translate-x-1'}`} />
    </button>
  )
}

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [state, setState] = useState<'idle' | 'ok' | 'fail'>('idle')
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setState('ok')
    } catch {
      setState('fail')
    }
    setTimeout(() => setState('idle'), 2000)
  }
  return (
    <button type="button" className="btn-secondary" onClick={() => void copy()}>
      {state === 'ok' ? 'Copied' : state === 'fail' ? 'Copy failed' : label}
      <span className="sr-only" aria-live="polite">{state === 'ok' ? 'Copied to clipboard' : ''}</span>
    </button>
  )
}

export function Snippet({ title, code }: { title?: string; code: string }) {
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-slate-800">{title}</span>
        <CopyButton text={code} label={title ? `Copy` : 'Copy'} />
      </div>
      <pre className="code" tabIndex={0} aria-label={title ? `${title} snippet` : 'code snippet'}>
        <code>{code}</code>
      </pre>
    </div>
  )
}

const FOCUSABLE = 'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])'

export function Dialog({
  title, onClose, children, side = false, wide = false, footer, closeOnBackdrop = true,
}: { title: string; onClose: () => void; children: ReactNode; side?: boolean; wide?: boolean; footer?: ReactNode; closeOnBackdrop?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    const el = ref.current
    const first = el?.querySelector<HTMLElement>(FOCUSABLE)
    ;(first || el)?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onCloseRef.current()
        return
      }
      if (e.key === 'Tab' && el) {
        const items = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE))
        if (!items.length) {
          e.preventDefault()
          return
        }
        const a = items[0]
        const z = items[items.length - 1]
        if (e.shiftKey && (document.activeElement === a || document.activeElement === el)) {
          e.preventDefault()
          z.focus()
        } else if (!e.shiftKey && document.activeElement === z) {
          e.preventDefault()
          a.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      prev?.focus?.()
    }
  }, [])

  return (
    <div className={`fixed inset-0 z-50 flex ${side ? 'justify-end' : 'items-center justify-center p-4'}`}>
      <div className="absolute inset-0 bg-slate-900/60" aria-hidden="true" onClick={() => closeOnBackdrop && onClose()} />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`relative flex max-h-full flex-col bg-white text-slate-900 shadow-xl ${
          side ? `h-full w-full ${wide ? 'max-w-4xl' : 'max-w-2xl'}` : `w-full rounded-lg ${wide ? 'max-w-3xl' : 'max-w-lg'}`
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-200 bg-navy-900 px-4 py-3 text-white">
          <h2 id={titleId} className="text-lg font-semibold">{title}</h2>
          <button type="button" aria-label="Close" className="rounded px-2 py-1 text-xl hover:bg-navy-700" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-200 p-3">{footer}</div>}
      </div>
    </div>
  )
}

export function ConfirmDialog({
  title, message, confirmLabel = 'Confirm', danger, onConfirm, onCancel, busy,
}: { title: string; message: ReactNode; confirmLabel?: string; danger?: boolean; onConfirm: () => void; onCancel: () => void; busy?: boolean }) {
  return (
    <Dialog
      title={title}
      onClose={onCancel}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
          <button type="button" className={danger ? 'btn-danger' : 'btn-primary'} disabled={busy} onClick={onConfirm}>{confirmLabel}</button>
        </>
      }
    >
      <div className="text-sm">{message}</div>
    </Dialog>
  )
}

export function Table({ children, caption }: { children: ReactNode; caption?: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200">
        {caption && <caption className="sr-only">{caption}</caption>}
        {children}
      </table>
    </div>
  )
}
export function Th({ children, className = '' }: { children?: ReactNode; className?: string }) {
  return <th scope="col" className={`th bg-slate-50 ${className}`}>{children}</th>
}
