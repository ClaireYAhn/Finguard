import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, errMsg } from '../api'
import { RuleTrace } from '../components/RuleTrace'
import { buildSnippets } from '../components/snippets'
import { ActionChip, Callout, ConfirmDialog, CopyButton, Dialog, Empty, ErrorBox, PageHeader, Snippet, Spinner, Status, Switch, Table, Th, TierChip } from '../components/ui'
import { useApp } from '../context'
import { fmtTime, useFetch } from '../hooks'
import type { App, CheckResult, PolicyPack, Template } from '../types'

interface KeyResult { app: App; key: string; key_notice?: string }
interface TestResult { action: string; text: string; rules_fired: string[]; trace: CheckResult[]; engine: string; latency: any; pack: string; note?: string }

const csv = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)

function AppForm({ initial, packs, onSaved, onCancel }: { initial?: App; packs: { pack: string; title: string }[]; onSaved: (r: any) => void; onCancel: () => void }) {
  const [f, setF] = useState({
    name: initial?.name ?? '', owner: initial?.owner ?? '', business_unit: initial?.business_unit ?? '', description: initial?.description ?? '',
    risk_tier: initial?.risk_tier ?? 'limited', policy_pack: initial?.policy_pack ?? packs[0]?.pack ?? '', model: initial?.model ?? '',
    data_classes: (initial?.data_classes ?? []).join(', '), allowed_roles: (initial?.allowed_roles ?? ['user']).join(', '), default_role: initial?.default_role ?? 'user',
    tool_policy: JSON.stringify(initial?.tool_policy ?? { allowed_tools: [], blocked_tools: [], approval_required_tools: [], allowed_outbound_domains: [], tool_roles: {} }, null, 2),
  })
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr(null)
    let tp
    try { tp = JSON.parse(f.tool_policy) } catch { setErr('Tool policy must be valid JSON.'); return }
    const body = { ...f, data_classes: csv(f.data_classes), allowed_roles: csv(f.allowed_roles), tool_policy: tp }
    setBusy(true)
    try {
      const r = initial ? await api(`/api/apps/${initial.id}`, { method: 'PATCH', body }) : await api('/api/apps', { method: 'POST', body })
      onSaved(r)
    } catch (e2) { setErr(errMsg(e2)) } finally { setBusy(false) }
  }
  const field = (id: string, label: string, el?: 'textarea') => (
    <div>
      <label htmlFor={`af-${id}`} className="label">{label}</label>
      {el ? <textarea id={`af-${id}`} className="input font-mono" rows={5} value={(f as any)[id]} onChange={(e) => set(id, e.target.value)} />
        : <input id={`af-${id}`} className="input" value={(f as any)[id]} onChange={(e) => set(id, e.target.value)} required={id === 'name'} />}
    </div>
  )
  return (
    <form onSubmit={(e) => void submit(e)} className="space-y-3">
      {field('name', 'Name')}{field('owner', 'Owner')}{field('business_unit', 'Business unit')}{field('description', 'Description')}
      <div className="grid grid-cols-2 gap-3">
        <div><label htmlFor="af-tier" className="label">Risk tier</label>
          <select id="af-tier" className="input" value={f.risk_tier} onChange={(e) => set('risk_tier', e.target.value)}>{['minimal', 'limited', 'high'].map((t) => <option key={t}>{t}</option>)}</select></div>
        <div><label htmlFor="af-pack" className="label">Policy pack</label>
          <select id="af-pack" className="input" value={f.policy_pack} onChange={(e) => set('policy_pack', e.target.value)} required>
            {packs.map((p) => <option key={p.pack} value={p.pack}>{p.title} ({p.pack})</option>)}
          </select></div>
      </div>
      {field('model', 'Model')}{field('data_classes', 'Data classes (comma separated)')}{field('allowed_roles', 'Allowed roles (comma separated)')}{field('default_role', 'Default role')}
      {field('tool_policy', 'Tool policy (JSON)', 'textarea')}
      {err && <p role="alert" className="text-sm text-red-800">{err}</p>}
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn-primary" disabled={busy}>{busy ? 'Saving…' : initial ? 'Save changes' : 'Create app'}</button>
      </div>
    </form>
  )
}

function KeyModal({ r, onClose }: { r: KeyResult; onClose: () => void }) {
  return (
    <Dialog title={`App key for ${r.app.name}`} onClose={onClose} closeOnBackdrop={false} footer={<button type="button" className="btn-primary" onClick={onClose}>I have saved the key</button>}>
      <Callout tone="warn"><strong>This key is shown once and cannot be shown again.</strong> Copy it now and store it securely. If you lose it, rotate the key.</Callout>
      <label htmlFor="newkey" className="label mt-3">App key</label>
      <div className="flex gap-2">
        <input id="newkey" readOnly className="input font-mono" value={r.key} onFocus={(e) => e.currentTarget.select()} />
        <CopyButton text={r.key} label="Copy key" />
      </div>
      {r.key_notice && <p className="mt-2 text-sm text-slate-800">{r.key_notice}</p>}
    </Dialog>
  )
}

function TemplateModal({ templates, onClose, onCreated }: { templates: Template[]; onClose: () => void; onCreated: (r: KeyResult) => void }) {
  const [sel, setSel] = useState<string>(templates[0]?.key ?? '')
  const [name, setName] = useState('')
  const [owner, setOwner] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const t = templates.find((x) => x.key === sel)
  const go = async () => {
    setBusy(true); setErr(null)
    try { onCreated(await api('/api/apps/from-template', { method: 'POST', body: { template: sel, name: name || undefined, owner: owner || undefined } })) }
    catch (e) { setErr(errMsg(e)) } finally { setBusy(false) }
  }
  return (
    <Dialog title="Create app from template" wide onClose={onClose} footer={<><button type="button" className="btn-secondary" onClick={onClose}>Cancel</button><button type="button" className="btn-primary" disabled={busy || !sel} onClick={() => void go()}>Create from template</button></>}>
      <div className="grid gap-4 md:grid-cols-2">
        <fieldset><legend className="label">Template</legend>
          <div className="max-h-72 space-y-1 overflow-y-auto">
            {templates.map((x) => (
              <label key={x.key} className={`flex cursor-pointer items-start gap-2 rounded border p-2 text-sm ${sel === x.key ? 'border-navy-800 bg-navy-50' : 'border-slate-300'}`}>
                <input type="radio" name="tpl" checked={sel === x.key} onChange={() => setSel(x.key)} />
                <span><strong>{x.name}</strong> <TierChip tier={x.risk_tier} /></span>
              </label>
            ))}
          </div></fieldset>
        <div className="space-y-3 text-sm">
          {t && <><p>{t.description}</p><Callout><strong>EU AI Act note:</strong> {t.eu_ai_act_note} <em>(illustrative, not legal advice)</em></Callout></>}
          <div><label htmlFor="tn" className="label">Name (optional)</label><input id="tn" className="input" value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><label htmlFor="to" className="label">Owner (optional)</label><input id="to" className="input" value={owner} onChange={(e) => setOwner(e.target.value)} /></div>
          {err && <p role="alert" className="text-red-800">{err}</p>}
        </div>
      </div>
    </Dialog>
  )
}

function ConnectDrawer({ app, newKey, onClose }: { app: App; newKey?: string; onClose: () => void }) {
  const { config } = useApp()
  const [tab, setTab] = useState('anthropic')
  const snippets = buildSnippets(app, config?.public_url || '', newKey)
  const cur = snippets.find((s) => s.id === tab) || snippets[0]
  const [msg, setMsg] = useState('')
  const [role, setRole] = useState(app.default_role || app.allowed_roles?.[0] || 'user')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<TestResult | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const send = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setErr(null); setRes(null)
    try { setRes(await api(`/api/apps/${app.id}/test`, { method: 'POST', body: { message: msg, role } })) }
    catch (e2) { setErr(errMsg(e2)) } finally { setBusy(false) }
  }
  return (
    <Dialog side wide title={`Connect: ${app.name}`} onClose={onClose}>
      <p className="mb-2 text-sm">Gateway base URL: <code className="font-mono">{config?.public_url}</code>. {newKey ? 'The snippets below contain the key you just created.' : <>Replace <code>YOUR_FINGUARD_APP_KEY</code> with the app key (key prefix <code>{app.key_prefix}</code>; rotate to get a new full key).</>}</p>
      <div role="tablist" aria-label="Integration snippets" className="mb-3 flex flex-wrap gap-1">
        {snippets.map((s) => (
          <button key={s.id} role="tab" type="button" id={`tab-${s.id}`} aria-selected={tab === s.id} aria-controls="snip-panel" onClick={() => setTab(s.id)}
            className={`btn ${tab === s.id ? 'border-navy-800 bg-navy-800 text-white' : 'border-slate-400 bg-white text-slate-900'}`}>{s.label}</button>
        ))}
      </div>
      <div role="tabpanel" id="snip-panel" aria-labelledby={`tab-${cur.id}`}>{cur.items.map((i) => <Snippet key={i.title} {...i} />)}</div>

      <section className="mt-6 border-t pt-4" aria-labelledby="testh">
        <h3 id="testh" className="mb-2 font-semibold">Send test request</h3>
        <form onSubmit={(e) => void send(e)} className="space-y-2">
          <label htmlFor="tmsg" className="label">Message</label>
          <textarea id="tmsg" className="input" rows={3} value={msg} onChange={(e) => setMsg(e.target.value)} required />
          <label htmlFor="trole" className="label">Role</label>
          <select id="trole" className="input w-auto" value={role} onChange={(e) => setRole(e.target.value)}>
            {(app.allowed_roles?.length ? app.allowed_roles : [role]).map((r) => <option key={r}>{r}</option>)}
          </select>
          <div><button type="submit" className="btn-primary" disabled={busy || !app.enabled}>{busy ? 'Sending…' : 'Send test request'}</button>
            {!app.enabled && <span className="ml-2 text-sm text-amber-900">App is disabled; enable it to test.</span>}</div>
        </form>
        <div aria-live="polite" className="mt-3">
          {busy && <Spinner label="Running through the guard…" />}
          {err && <ErrorBox message={err} />}
          {res && (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2"><ActionChip action={res.action} /><span>engine {res.engine}</span></div>
              <div><div className="text-xs font-semibold text-slate-700">Final text</div><div className="whitespace-pre-wrap rounded border border-slate-300 bg-white p-2">{res.text}</div></div>
              <div><span className="text-xs font-semibold text-slate-700">Rules fired: </span>{res.rules_fired.length ? res.rules_fired.map((r) => <span key={r} className="chip mr-1 bg-slate-100 font-mono ring-1 ring-slate-400">{r}</span>) : 'none'}</div>
              {res.note && <p className="text-slate-700">{res.note}</p>}
              <details><summary className="cursor-pointer font-medium">Trace ({res.trace.length} checks)</summary><div className="mt-2"><RuleTrace trace={res.trace} /></div></details>
            </div>
          )}
        </div>
      </section>
    </Dialog>
  )
}

export default function Apps() {
  const { config } = useApp()
  const apps = useFetch<App[]>('apps', () => api('/api/apps'))
  const [packs, setPacks] = useState<{ pack: string; title: string }[]>([])
  const [templates, setTemplates] = useState<Template[]>([])
  const [form, setForm] = useState<{ app?: App } | null>(null)
  const [tpl, setTpl] = useState(false)
  const [keyRes, setKeyRes] = useState<KeyResult | null>(null)
  const [connect, setConnect] = useState<{ app: App; key?: string } | null>(null)
  const [del, setDel] = useState<App | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<PolicyPack[]>('/api/policies').then(setPacks).catch(() => undefined)
    api<Template[]>('/api/templates').then(setTemplates).catch(() => undefined)
  }, [])

  const created = (r: KeyResult) => { setForm(null); setTpl(false); setKeyRes(r); setMsg(`App "${r.app.name}" created.`); apps.reload() }
  const toggle = async (a: App) => {
    try { await api(`/api/apps/${a.id}`, { method: 'PATCH', body: { enabled: !a.enabled } }); setMsg(`${a.name} ${a.enabled ? 'disabled' : 'enabled'}.`); apps.reload() }
    catch (e) { setMsg(errMsg(e)) }
  }
  const rotate = async (a: App) => {
    try { const r = await api<KeyResult>(`/api/apps/${a.id}/rotate-key`, { method: 'POST' }); setKeyRes(r); setMsg(`Key rotated for ${a.name}.`); apps.reload() }
    catch (e) { setMsg(errMsg(e)) }
  }
  const remove = async () => {
    if (!del) return
    setBusy(true)
    try { await api(`/api/apps/${del.id}`, { method: 'DELETE' }); setMsg(`${del.name} deleted.`); setDel(null); apps.reload() }
    catch (e) { setMsg(errMsg(e)); setDel(null) } finally { setBusy(false) }
  }

  return (
    <div>
      <PageHeader title="Apps">
        <button type="button" className="btn-primary" onClick={() => setForm({})}>Create app</button>
        <button type="button" className="btn-secondary" onClick={() => setTpl(true)} disabled={templates.length === 0}>Create from template</button>
      </PageHeader>
      {config?.scope_note && <div className="mb-3"><Callout><strong>Scope:</strong> {config.scope_note}</Callout></div>}
      <Status>{msg}</Status>
      {apps.error && <ErrorBox message={apps.error} onRetry={apps.reload} />}
      {apps.loading && <Spinner />}
      {apps.data && apps.data.length === 0 && <Empty>No apps registered yet. Create one, use a template, or seed demo apps from the Overview page.</Empty>}
      {apps.data && apps.data.length > 0 && (
        <Table caption="Registered apps">
          <thead><tr><Th>Name</Th><Th>Status</Th><Th>Risk tier</Th><Th>Owner</Th><Th>Policy pack</Th><Th>Last activity</Th><Th>7d requests</Th><Th>7d blocks</Th><Th>Actions</Th></tr></thead>
          <tbody className="divide-y divide-slate-200">
            {apps.data.map((a) => (
              <tr key={a.id}>
                <th scope="row" className="td text-left font-medium">{a.name}{a.is_demo && <span className="chip ml-1 bg-slate-100 ring-1 ring-slate-400">demo</span>}</th>
                <td className="td"><div className="flex items-center gap-2"><Switch checked={a.enabled} onChange={() => void toggle(a)} label={`${a.enabled ? 'Disable' : 'Enable'} ${a.name}`} /><span>{a.enabled ? 'enabled' : 'disabled'}</span></div></td>
                <td className="td"><TierChip tier={a.risk_tier} /></td>
                <td className="td">{a.owner}</td>
                <td className="td"><Link className="text-navy-800 underline" to={`/policies?pack=${encodeURIComponent(a.policy_pack)}`}>{a.policy_pack}</Link></td>
                <td className="td">{fmtTime(a.last_activity)}</td>
                <td className="td">{a.requests_7d ?? 0}</td><td className="td">{a.blocked_7d ?? 0}</td>
                <td className="td"><div className="flex flex-wrap gap-1">
                  <button type="button" className="btn-secondary" onClick={() => setConnect({ app: a })}>Connect</button>
                  <button type="button" className="btn-secondary" onClick={() => setForm({ app: a })} aria-label={`Edit ${a.name}`}>Edit</button>
                  <button type="button" className="btn-secondary" onClick={() => void rotate(a)} aria-label={`Rotate key for ${a.name}`}>Rotate key</button>
                  <button type="button" className="btn-danger" onClick={() => setDel(a)} aria-label={`Delete ${a.name}`}>Delete</button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {form && <Dialog side title={form.app ? `Edit ${form.app.name}` : 'Create app'} onClose={() => setForm(null)}>
        <AppForm initial={form.app} packs={packs} onCancel={() => setForm(null)} onSaved={(r) => { if (form.app) { setForm(null); setMsg('App updated.'); apps.reload() } else created(r) }} /></Dialog>}
      {tpl && <TemplateModal templates={templates} onClose={() => setTpl(false)} onCreated={created} />}
      {keyRes && <KeyModal r={keyRes} onClose={() => { const k = keyRes; setKeyRes(null); setConnect({ app: k.app, key: k.key }) }} />}
      {connect && <ConnectDrawer app={connect.app} newKey={connect.key} onClose={() => setConnect(null)} />}
      {del && <ConfirmDialog danger title="Delete app" busy={busy} confirmLabel="Delete" message={<>Delete <strong>{del.name}</strong>? Its key stops working immediately. Audit records are kept.</>} onConfirm={() => void remove()} onCancel={() => setDel(null)} />}
    </div>
  )
}
