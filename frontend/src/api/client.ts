import type { PipelineResult, RunRequest } from '../types/pipeline'

export async function runPipeline(body: RunRequest = {}): Promise<PipelineResult> {
  const response = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail)
  }

  return response.json() as Promise<PipelineResult>
}
