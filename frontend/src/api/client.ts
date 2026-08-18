import type {
  AgentRequest,
  AgentResult,
  BacktestRequest,
  BacktestResult,
  PipelineResult,
  RunRequest,
} from '../types/pipeline'

/** Per-endpoint ceilings. A run that exceeds these is hung, not slow: a live
 *  snapshot is sub-second, a 3y backtest ~15s, an agent loop a few minutes. */
export const TIMEOUTS = {
  run: 60_000,
  backtest: 180_000,
  agent: 600_000,
} as const

/** Thrown when the caller aborted deliberately, so the UI can stay silent
 *  instead of reporting a failure the user caused on purpose. */
export class CancelledError extends Error {
  constructor() {
    super('Request cancelled')
    this.name = 'CancelledError'
  }
}

export function isCancelled(err: unknown): boolean {
  return err instanceof CancelledError
}

export type RequestOptions = {
  /** Caller's cancellation signal, combined with the timeout. */
  signal?: AbortSignal
  /** Override the per-endpoint default. */
  timeoutMs?: number
}

async function postJson<T>(
  url: string,
  body: unknown,
  defaultTimeoutMs: number,
  options: RequestOptions = {},
): Promise<T> {
  const timeoutMs = options.timeoutMs ?? defaultTimeoutMs
  const timeout = AbortSignal.timeout(timeoutMs)
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout

  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (err) {
    // Distinguish "the user pressed Cancel" from "the server never answered".
    if (options.signal?.aborted) throw new CancelledError()
    if (timeout.aborted) {
      throw new Error(
        `The API did not respond within ${Math.round(timeoutMs / 1000)}s. ` +
          'It may still be working — check the uvicorn console, or try a shorter window.',
      )
    }
    throw err
  }

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

export async function runPipeline(
  body: RunRequest = {},
  options?: RequestOptions,
): Promise<PipelineResult> {
  return postJson<PipelineResult>('/api/run', body, TIMEOUTS.run, options)
}

export async function runBacktest(
  body: BacktestRequest = {},
  options?: RequestOptions,
): Promise<BacktestResult> {
  return postJson<BacktestResult>('/api/backtest', body, TIMEOUTS.backtest, options)
}

export async function runAgent(
  body: AgentRequest = {},
  options?: RequestOptions,
): Promise<AgentResult> {
  return postJson<AgentResult>('/api/agent', body, TIMEOUTS.agent, options)
}
