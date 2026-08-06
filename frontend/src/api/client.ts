import type {
  AgentRequest,
  AgentResult,
  BacktestRequest,
  BacktestResult,
  PipelineResult,
  RunRequest,
} from '../types/pipeline'

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const payload = (await response.json()) as { detail?: string | { msg?: string }[] }
      if (typeof payload.detail === 'string') {
        detail = payload.detail
      } else if (Array.isArray(payload.detail)) {
        detail = payload.detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
      }
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}

export async function runPipeline(body: RunRequest = {}): Promise<PipelineResult> {
  return postJson<PipelineResult>('/api/run', body)
}

export async function runBacktest(body: BacktestRequest = {}): Promise<BacktestResult> {
  return postJson<BacktestResult>('/api/backtest', body)
}

export async function runAgent(body: AgentRequest = {}): Promise<AgentResult> {
  return postJson<AgentResult>('/api/agent', body)
}
