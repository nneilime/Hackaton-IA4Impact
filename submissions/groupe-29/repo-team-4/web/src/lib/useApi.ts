import { DependencyList, useCallback, useEffect, useRef, useState } from "react"

export type ApiState<T> = {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => Promise<void>
}

/** Runs `load` on mount and whenever `deps` change; `reload` runs it again (e.g. after an action). */
export function useApi<T>(load: () => Promise<T>, deps: DependencyList): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const latest = useRef(0)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps)

  const reload = useCallback(async () => {
    const call = ++latest.current
    setLoading(true)
    try {
      const value = await run()
      if (call === latest.current) {
        setData(value)
        setError(null)
      }
    } catch (e) {
      if (call === latest.current) setError(e instanceof Error ? e.message : String(e))
    } finally {
      if (call === latest.current) setLoading(false)
    }
  }, [run])

  useEffect(() => {
    reload()
  }, [reload])

  return { data, error, loading, reload }
}
