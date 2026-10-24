import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errMsg } from '../api'
import { Banner } from '../components/Layout'
import { useApp } from '../context'

export default function Login() {
  const { setSignedIn, refreshConfig, config } = useApp()
  const nav = useNavigate()
  const [pw, setPw] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await api('/api/auth/login', { method: 'POST', body: { password: pw } })
      await refreshConfig()
      setSignedIn(true)
      nav('/')
    } catch (e2) {
      setErr(errMsg(e2))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen">
      <Banner />
      <main className="mx-auto mt-12 max-w-sm px-4">
        <div className="card">
          <h1 className="mb-1 text-2xl font-bold text-navy-900">FinGuard</h1>
          <p className="mb-4 text-sm text-slate-800">Sign in to the control panel{config ? ` (v${config.version})` : ''}.</p>
          <form onSubmit={(e) => void submit(e)}>
            <label htmlFor="pw" className="label">Admin password</label>
            <input id="pw" type="password" autoComplete="current-password" className="input mb-3" value={pw} onChange={(e) => setPw(e.target.value)} required />
            <div aria-live="assertive">{err && <p role="alert" className="mb-3 text-sm text-red-800">{err}</p>}</div>
            <button type="submit" className="btn-primary w-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
          </form>
        </div>
      </main>
    </div>
  )
}
