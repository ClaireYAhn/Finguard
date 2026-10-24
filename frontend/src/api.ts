export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const UNAUTHORIZED_EVENT = 'fg-unauthorized'

function detailMessage(body: any, status: number, statusText: string): string {
  const d = body?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x) => (x?.msg ? `${(x.loc || []).join('.')}: ${x.msg}` : String(x))).join('; ')
  if (d) return JSON.stringify(d)
  return `Request failed (${status}${statusText ? ' ' + statusText : ''})`
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      method: opts.method || 'GET',
      credentials: 'include',
      headers: opts.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the FinGuard backend. Check that it is running and try again.')
  }
  const text = await res.text()
  let body: any = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = null
    }
  }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/api/auth/login')) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    }
    throw new ApiError(res.status, detailMessage(body, res.status, res.statusText))
  }
  return body as T
}

export function qs(params: Record<string, string | number | undefined | null>): string {
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') u.set(k, String(v))
  const s = u.toString()
  return s ? `?${s}` : ''
}

export function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}
