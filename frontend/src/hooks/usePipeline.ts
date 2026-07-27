import { useCallback, useState } from 'react'
import { runPipeline } from '../api/client'
import type { PipelineResult, RunRequest } from '../types/pipeline'

type PipelineState = {
  data: PipelineResult | null
  loading: boolean
  error: string | null
  run: (request?: RunRequest) => Promise<void>
}

export function usePipeline(): PipelineState {
  const [data, setData] = useState<PipelineResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async (request: RunRequest = {}) => {
    setLoading(true)
    setError(null)
    try {
      const result = await runPipeline(request)
      setData(result)
    } catch (err) {
      setData(null)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  return { data, loading, error, run }
}
