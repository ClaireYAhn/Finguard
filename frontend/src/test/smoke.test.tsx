import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AppProvider } from '../context'
import { wordDiff } from '../components/diff'

const config = {
  version: '1.0', provider: 'mock', mock: true, engine: 'native', store_raw: true, model_judge: false, public_url: 'http://localhost:8000',
  banner: '', engine_status: { nemo_loaded: false, nemo_version: null, last_error: null }, signed_in: true, scope_note: 'Scope note here',
}
const overview = {
  days: 7, cards: { requests: 10, blocked: 2, modified: 1, escalated: 1, allowed: 6, open_reviews: 1, apps_live: 1, apps_idle: 0, apps_total: 1 },
  series: [{ t: '2026-01-01', allow: 6, modify: 1, block: 2, escalate: 1, total: 10 }], bucket: 'day',
  per_app: [{ app_id: 'a1', app: 'Test App', tier: 'high', requests: 10, blocked: 2, modified: 1, escalated: 1, violation_rate: 0.4 }],
  per_rule: [], top_rules: [], heatmap: [{ app: 'Test App', tier: 'high', requests: 10, violation_rate: 0.4 }],
  attention: [{ kind: 'no_activity', app_id: 'a1', app: 'Test App', detail: 'idle' }], simulated_requests: 5, simulated_share: 0.5, channels: {},
}
const app = { id: 'a1', name: 'Test App', owner: 'o', business_unit: 'b', description: '', risk_tier: 'high', eu_ai_act_note: '', model: 'm', data_classes: [], policy_pack: 'p', allowed_roles: ['user'], default_role: 'user', tool_policy: {}, enabled: true, created_at: '', key_prefix: 'fg_', template: null, is_demo: false }

function route(url: string): unknown {
  if (url.startsWith('/api/config')) return config
  if (url.startsWith('/api/overview')) return overview
  if (url.startsWith('/api/apps')) return [app]
  if (url.startsWith('/api/templates')) return []
  if (url.startsWith('/api/reviews')) return []
  if (url.startsWith('/api/audit/verify')) return { ok: true, count: 0, head_hash: '', broken_at: null, audit_id: null, message: 'ok' }
  if (url.startsWith('/api/audit')) return []
  if (url.startsWith('/api/policies')) return []
  if (url.startsWith('/api/eval/latest')) return null
  if (url.startsWith('/api/demo/scenarios')) return []
  return {}
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(route(url)), { status: 200 })))
})
afterEach(() => vi.unstubAllGlobals())

function mount(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><AppProvider><App /></AppProvider></MemoryRouter>)
}

describe('pages mount', () => {
  it('shows the banner and overview with simulated share', async () => {
    mount('/')
    expect(await screen.findByText('50.0%')).toBeInTheDocument()
    expect(screen.getByText(/Demo data is fictional/)).toBeInTheDocument()
  })
  for (const [path, heading] of [
    ['/apps', 'Apps'], ['/live', 'Live traffic'], ['/reviews', 'Review queue'], ['/policies', 'Policies'], ['/evaluation', 'Evaluation'],
    ['/audit', 'Audit'], ['/reports', 'Reports'], ['/demo', 'Demo'], ['/about', 'About FinGuard'],
  ] as const) {
    it(`mounts ${path}`, async () => {
      mount(path)
      expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
    })
  }
  it('shows login when signed out', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ...config, signed_in: false }), { status: 200 })))
    mount('/apps')
    await waitFor(() => expect(screen.getByLabelText('Admin password')).toBeInTheDocument())
    expect(screen.getByText(/Demo data is fictional/)).toBeInTheDocument()
  })
})

describe('wordDiff', () => {
  it('marks deletions and insertions', () => {
    const d = wordDiff('a b c', 'a x c')
    expect(d.some((p) => p.type === 'del' && p.text.includes('b'))).toBe(true)
    expect(d.some((p) => p.type === 'ins' && p.text.includes('x'))).toBe(true)
  })
})
