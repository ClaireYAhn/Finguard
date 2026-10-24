import { useCallback, useEffect, useRef, useState } from 'react'
import { errMsg } from './api'

export interface Fetched<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

/** Fetch on mount and whenever `key` changes; optional polling. */
export function useFetch<T>(key: string, fn: () => Promise<T>, opts: { interval?: number; paused?: boolean } = {}): Fetched<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const fnRef = useRef(fn)
  fnRef.current = fn
  const [tick, setTick] = useState(0)
  const { interval, paused } = opts

  useEffect(() => {
    let alive = true
    const run = async (initial: boolean) => {
      if (initial) setLoading(true)
      try {
        const r = await fnRef.current()
        if (alive) {
          setData(r)
          setError(null)
        }
      } catch (e) {
        if (alive) setError(errMsg(e))
      } finally {
        if (alive && initial) setLoading(false)
      }
    }
    void run(true)
    let id: number | undefined
    if (interval && !paused) id = window.setInterval(() => void run(false), interval)
    return () => {
      alive = false
      if (id) window.clearInterval(id)
    }
  }, [key, interval, paused, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}

export function useLocalStorage(key: string): [string | null, (v: string) => void] {
  const read = () => {
    try {
      return localStorage.getItem(key)
    } catch {
      return null
    }
  }
  const [val, setVal] = useState<string | null>(read)
  const set = (v: string) => {
    setVal(v)
    try {
      localStorage.setItem(key, v)
    } catch {
      /* storage unavailable */
    }
  }
  return [val, set]
}

export function fmtTime(ts?: string | null): string {
  if (!ts) return '-'
  const d = new Date(ts)
  return isNaN(d.getTime()) ? ts : d.toLocaleString()
}
export function pct(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined ? 'n/a' : `${(v * 100).toFixed(digits)}%`
}
export function ms(v: number | null | undefined): string {
  return v === null || v === undefined ? 'n/a' : `${Number(v).toFixed(1)} ms`
}
