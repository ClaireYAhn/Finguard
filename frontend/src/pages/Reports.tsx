import { useState } from 'react'
import { api, qs } from '../api'
import { Callout, Empty, ErrorBox, PageHeader, Spinner } from '../components/ui'
import { useFetch } from '../hooks'
import type { App } from '../types'

export default function Reports() {
  const apps = useFetch<App[]>('rep-apps', () => api('/api/apps'))
  const [appId, setAppId] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [shown, setShown] = useState<string | null>(null)
  const id = appId || apps.data?.[0]?.id || ''
  const url = id ? `/api/reports/${encodeURIComponent(id)}${qs({ from, to })}` : ''
  return (
    <div>
      <PageHeader title="Reports" />
      <div className="mb-3"><Callout>Reports are printable HTML pages. Open one in a new tab and use your browser&apos;s Print command, then choose &quot;Save as PDF&quot;.</Callout></div>
      {apps.error && <ErrorBox message={apps.error} onRetry={apps.reload} />}
      {apps.loading && <Spinner />}
      {apps.data && apps.data.length === 0 && <Empty>No apps yet, so there is nothing to report on.</Empty>}
      {apps.data && apps.data.length > 0 && (
        <>
          <div className="card mb-4 flex flex-wrap items-end gap-3">
            <div><label htmlFor="ra" className="label">App</label><select id="ra" className="input" value={id} onChange={(e) => setAppId(e.target.value)}>{apps.data.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
            <div><label htmlFor="rf" className="label">From date</label><input id="rf" type="date" className="input" value={from} onChange={(e) => setFrom(e.target.value)} /></div>
            <div><label htmlFor="rt" className="label">To date</label><input id="rt" type="date" className="input" value={to} onChange={(e) => setTo(e.target.value)} /></div>
            <a className="btn-primary" href={url} target="_blank" rel="noreferrer">Open report (new tab)</a>
            <button type="button" className="btn-secondary" onClick={() => setShown(url)}>Preview below</button>
          </div>
          {shown && <iframe title="Report preview" src={shown} className="h-[70vh] w-full rounded-lg border border-slate-300 bg-white" />}
        </>
      )}
    </div>
  )
}
