import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { PresentationCtx, useApp } from '../context'
import { useFetch } from '../hooks'
import type { ReviewCase } from '../types'

export function Banner() {
  return (
    <div role="note" className="bg-amber-300 px-4 py-2 text-center text-sm font-semibold text-slate-900">
      Demo data is fictional. Not financial, legal or regulatory advice.
    </div>
  )
}

const NAV: [string, string][] = [
  ['/', 'Overview'], ['/apps', 'Apps'], ['/live', 'Live traffic'], ['/reviews', 'Review queue'], ['/policies', 'Policies'],
  ['/evaluation', 'Evaluation'], ['/audit', 'Audit'], ['/reports', 'Reports'], ['/demo', 'Demo'], ['/about', 'About'],
]

export default function Layout() {
  const { config, setSignedIn } = useApp()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  const [presentation, setPresentation] = useState(false)
  const reviews = useFetch<ReviewCase[]>('nav-reviews', () => api('/api/reviews?status=open'), { interval: 20000 })
  const openCount = reviews.data?.length

  useEffect(() => setOpen(false), [loc.pathname])

  const logout = async () => {
    try { await api('/api/auth/logout', { method: 'POST' }) } catch { /* ignore */ }
    setSignedIn(false)
    nav('/login')
  }

  const links = (
    <ul className="space-y-1">
      {NAV.map(([to, label]) => (
        <li key={to}>
          <NavLink
            to={to}
            end={to === '/'}
            className={({ isActive }) => `flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium ${isActive ? 'bg-white text-navy-900' : 'text-white hover:bg-navy-700'}`}
          >
            {label}
            {to === '/reviews' && openCount !== undefined && openCount > 0 && (
              <span className="ml-2 rounded-full bg-amber-300 px-2 text-xs font-bold text-slate-900" aria-label={`${openCount} open reviews`}>{openCount}</span>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  )

  return (
    <PresentationCtx.Provider value={{ presentation, setPresentation }}>
      <div className="min-h-screen">
        <Banner />
        <div className="md:flex">
          {!presentation && (
            <>
              <header className="flex items-center justify-between bg-navy-900 px-4 py-3 text-white md:hidden">
                <span className="font-bold">FinGuard</span>
                <button type="button" className="btn border-white text-white" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen(!open)}>
                  {open ? 'Close menu' : 'Menu'}
                </button>
              </header>
              <nav id="mobile-nav" aria-label="Main" className={`${open ? 'block' : 'hidden'} bg-navy-800 p-3 md:hidden`}>{links}</nav>
              <aside className="hidden min-h-[calc(100vh-36px)] w-56 shrink-0 flex-col bg-navy-900 p-3 text-white md:flex">
                <div className="mb-4 px-3 pt-2">
                  <div className="text-xl font-bold">FinGuard</div>
                  <div className="text-xs text-slate-200">Control panel v{config?.version}</div>
                </div>
                <nav aria-label="Main" className="flex-1">{links}</nav>
                <button type="button" className="btn mt-4 border-white text-white hover:bg-navy-700" onClick={() => void logout()}>Sign out</button>
              </aside>
              <div className="px-4 pb-2 pt-2 md:hidden"><button type="button" className="btn-secondary" onClick={() => void logout()}>Sign out</button></div>
            </>
          )}
          <main id="main" className="min-w-0 flex-1 p-4 md:p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </PresentationCtx.Provider>
  )
}
