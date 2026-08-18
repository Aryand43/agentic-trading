import { useCallback, useEffect, useRef, useState } from 'react'
import {
  isCancelled,
  runAgent,
  runBacktest,
  runPipeline,
  type RequestOptions,
} from '../api/client'
import type {
  AgentRequest,
  AgentResult,
  BacktestRequest,
  BacktestResult,
  PipelineResult,
  RunRequest,
} from '../types/pipeline'

type AsyncState<T> = {
  data: T | null
  loading: boolean
  error: string | null
}

export type AsyncAction<TReq, TRes> = AsyncState<TRes> & {
  run: (request?: TReq) => Promise<TRes | null>
  clear: () => void
  /** Drop the error without discarding data. Used to clear one mode's stale
   *  failure when another mode starts a run. */
  clearError: () => void
  /** Abort the in-flight request, if any. */
  cancel: () => void
}

function useAsyncAction<TReq, TRes>(
  action: (req: TReq, options?: RequestOptions) => Promise<TRes>,
): AsyncAction<TReq, TRes> {
  const [data, setData] = useState<TRes | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  // Abort anything still in flight if the app unmounts.
  useEffect(() => () => controllerRef.current?.abort(), [])

  const run = useCallback(
    async (request: TReq = {} as TReq): Promise<TRes | null> => {
      // A new run supersedes an older one rather than racing it.
      controllerRef.current?.abort()
      const controller = new AbortController()
      controllerRef.current = controller

      setLoading(true)
      setError(null)
      try {
        const result = await action(request, { signal: controller.signal })
        setData(result)
        return result
      } catch (err) {
        // A deliberate cancel is not a failure; leave prior data on screen.
        if (isCancelled(err)) return null
        setData(null)
        setError(err instanceof Error ? err.message : 'Unknown error')
        return null
      } finally {
        // Only the newest run owns the loading flag.
        if (controllerRef.current === controller) {
          controllerRef.current = null
          setLoading(false)
        }
      }
    },
    [action],
  )

  const clear = useCallback(() => {
    setData(null)
    setError(null)
  }, [])

  const clearError = useCallback(() => setError(null), [])

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    setLoading(false)
  }, [])

  return { data, loading, error, run, clear, clearError, cancel }
}

export function usePipeline() {
  return useAsyncAction<RunRequest, PipelineResult>(runPipeline)
}

export function useBacktest() {
  return useAsyncAction<BacktestRequest, BacktestResult>(runBacktest)
}

export function useAgent() {
  return useAsyncAction<AgentRequest, AgentResult>(runAgent)
}
