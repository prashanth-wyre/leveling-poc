import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

/** Load a resource; `reload()` fetches again. A 404 is reported as `missing`, not as an error. */
export function useResource<T = any>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [missing, setMissing] = useState(false)
  const [loading, setLoading] = useState(!!path)
  const seq = useRef(0)
  const reload = useCallback(async () => {
    if (!path) return
    const my = ++seq.current
    setLoading(true)
    try {
      const d = await api<T>(path)
      if (my === seq.current) { setData(d); setError(null); setMissing(false) }
    } catch (e: any) {
      if (my !== seq.current) return
      if (e.status === 404) { setMissing(true); setData(null) } else setError(e.message)
    } finally {
      if (my === seq.current) setLoading(false)
    }
  }, [path])
  useEffect(() => { setData(null); reload() }, [reload])
  return { data, error, missing, loading, reload, setData }
}

/** Poll a leveling run while it is running; calls onDone once when it finishes. */
export function useRun(pid: string | undefined, onDone: () => void) {
  const [run, setRun] = useState<any>(null)
  const done = useRef(onDone)
  done.current = onDone
  const timer = useRef<number>()
  const tick = useCallback(async () => {
    if (!pid) return
    try {
      const r = await api(`/packages/${pid}/run`)
      setRun(r)
      if (r.status === 'running') timer.current = window.setTimeout(tick, 1000)
      else if (r.status === 'done' || r.status === 'error') { if (r.status === 'done') done.current(); }
    } catch { timer.current = window.setTimeout(tick, 2000) }
  }, [pid])
  const watch = useCallback((r?: any) => { if (r) setRun(r); window.clearTimeout(timer.current); timer.current = window.setTimeout(tick, 600) }, [tick])
  useEffect(() => {
    if (!pid) return
    api(`/packages/${pid}/run`).then((r) => { setRun(r); if (r.status === 'running') watch() }).catch(() => {})
    return () => window.clearTimeout(timer.current)
  }, [pid, watch])
  return { run, watch, clear: () => setRun(null) }
}
