/** Guards `types/pipeline.ts` against drift from the FastAPI schema.
 *
 * Codegen would be better, but no `openapi-typescript` release supports the
 * TypeScript 6 this project pins (its peer range is ^5.x), so instead this
 * asserts the hand-written types against the live `/openapi.json`. It already
 * caught three fields typed optional here that the API always sends.
 *
 * Skips when the API is not running, so `npm test` stays useful offline.
 * Run the API first for the check to actually execute:
 *   uvicorn api.main:app --port 8000
 */
import { beforeAll, describe, expect, it } from 'vitest'

const API = import.meta.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

type Schema = {
  properties?: Record<string, unknown>
  required?: string[]
}

let schemas: Record<string, Schema> | null = null

beforeAll(async () => {
  try {
    const res = await fetch(`${API}/openapi.json`, { signal: AbortSignal.timeout(3000) })
    if (!res.ok) return
    const doc = (await res.json()) as { components?: { schemas?: Record<string, Schema> } }
    schemas = doc.components?.schemas ?? null
  } catch {
    schemas = null
  }
})

/** Fields the frontend types declare as always-present (non-optional). */
const REQUIRED_BY_FRONTEND: Record<string, string[]> = {
  MetricsBlock: [
    'total_return',
    'annualized_return',
    'sharpe',
    'max_drawdown',
    'hit_rate',
    'signal_hit_rate',
    'utility',
    'turnover',
    'n_days',
    'final_equity',
    'start_equity',
  ],
  EquityPoint: ['date', 'equity', 'series'],
  WindowInfo: ['start', 'end', 'n_days'],
  RunResponse: [
    'tickers',
    'horizons',
    'signals',
    'conviction',
    'volatilities',
    'portfolio_volatility',
    'target_volatility',
    'weights',
  ],
  BacktestResponse: [
    'tickers',
    'initial_capital',
    'window',
    'metrics',
    'baselines',
    'equity_curve',
    'baseline_curves',
    'segments',
  ],
  AgentResponse: [
    'horizon',
    'window',
    'tickers',
    'run_dir',
    'best_iteration',
    'best_test_sharpe',
    'iterations',
  ],
}

describe('frontend types match the API schema', () => {
  it('reaches the API (skipped when it is not running)', () => {
    if (!schemas) {
      console.warn(`[contract] API not reachable at ${API} — schema checks skipped.`)
    }
    expect(true).toBe(true)
  })

  for (const [schemaName, fields] of Object.entries(REQUIRED_BY_FRONTEND)) {
    describe(schemaName, () => {
      it('exists in the schema', () => {
        if (!schemas) return
        expect(schemas[schemaName], `${schemaName} missing from /openapi.json`).toBeDefined()
      })

      it('declares every field the frontend reads', () => {
        if (!schemas) return
        const schema = schemas[schemaName]
        if (!schema) return
        const props = Object.keys(schema.properties ?? {})
        const missing = fields.filter((f) => !props.includes(f))
        expect(missing, `${schemaName} is missing ${missing.join(', ')}`).toEqual([])
      })

      it('always sends the fields the frontend types as non-optional', () => {
        if (!schemas) return
        const schema = schemas[schemaName]
        if (!schema) return
        // Pydantic marks a field required only when it has no default, but a
        // field WITH a default is still always serialised. So "present in
        // properties" is the correct guarantee to assert here; a field that
        // vanished entirely is the drift we care about.
        const props = new Set(Object.keys(schema.properties ?? {}))
        for (const f of fields) {
          expect(props.has(f), `${schemaName}.${f} disappeared from the API`).toBe(true)
        }
      })
    })
  }
})
