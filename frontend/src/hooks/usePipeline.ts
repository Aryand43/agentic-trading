import { useCallback, useState } from 'react'
import { runAgent, runBacktest, runPipeline } from '../api/client'
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

function useAsyncAction<TReq, TRes>(
  action: (req: TReq) => Promise<TRes>,
): AsyncState<TRes> & {
  run: (request?: TReq) => Promise<TRes | null>
  clear: () => void
} {
  const [data, setData] = useState<TRes | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(
    async (request: TReq = {} as TReq): Promise<TRes | null> => {
      setLoading(true)
      setError(null)
      try {
        const result = await action(request)
        setData(result)
        return result
      } catch (err) {
        setData(null)
        setError(err instanceof Error ? err.message : 'Unknown error')
        return null
      } finally {
        setLoading(false)
      }
    },
    [action],
  )

  const clear = useCallback(() => {
    setData(null)
    setError(null)
  }, [])

  return { data, loading, error, run, clear }
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
