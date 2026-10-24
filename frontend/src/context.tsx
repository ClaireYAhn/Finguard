import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, UNAUTHORIZED_EVENT } from './api'
import type { Config } from './types'

interface Ctx {
  config: Config | null
  configError: string | null
  signedIn: boolean
  setSignedIn: (v: boolean) => void
  refreshConfig: () => Promise<void>
}
const AppCtx = createContext<Ctx | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<Config | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)
  const [signedIn, setSignedIn] = useState(false)

  const refreshConfig = useCallback(async () => {
    try {
      const c = await api<Config>('/api/config')
      setConfig(c)
      setSignedIn(c.signed_in)
      setConfigError(null)
    } catch (e) {
      setConfigError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void refreshConfig()
  }, [refreshConfig])

  useEffect(() => {
    const h = () => setSignedIn(false)
    window.addEventListener(UNAUTHORIZED_EVENT, h)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, h)
  }, [])

  return <AppCtx.Provider value={{ config, configError, signedIn, setSignedIn, refreshConfig }}>{children}</AppCtx.Provider>
}

export function useApp(): Ctx {
  const c = useContext(AppCtx)
  if (!c) throw new Error('AppProvider missing')
  return c
}

interface Pres {
  presentation: boolean
  setPresentation: (v: boolean) => void
}
export const PresentationCtx = createContext<Pres>({ presentation: false, setPresentation: () => undefined })
export const usePresentation = () => useContext(PresentationCtx)
