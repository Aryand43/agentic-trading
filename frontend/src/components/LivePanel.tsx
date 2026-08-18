import { Suspense, lazy, useMemo, useState } from 'react'
import { HintLabel } from './Hint'
import { HINTS } from '../content/hints'
import { HorizonGrid } from './HorizonGrid'
import { MetaStrip } from './MetaStrip'
import { RiskLimitNotice } from './RiskLimitNotice'
import { ChartFallback } from './ChartFallback'
import { checkLimits } from '../lib/limits'
import type { PipelineResult } from '../types/pipeline'

const ConvictionChart = lazy(() =>
  import('./ConvictionChart').then((m) => ({ default: m.ConvictionChart })),
)
const WeightsChart = lazy(() =>
  import('./WeightsChart').then((m) => ({ default: m.WeightsChart })),
)

type Props = {
  data: PipelineResult
  /** The limits that were requested for this run, so the result can be checked. */
  requested: { maxPosition: number; grossExposure: number }
}

export function LivePanel({ data, requested }: Props) {
  const [open, setOpen] = useState(true)
  const breaches = useMemo(() => checkLimits(data.weights, requested), [data.weights, requested])

  return (
    <section className="border-t border-line pt-6 animate-[fadeIn_0.35s_ease-out]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-baseline justify-between gap-3 text-left"
      >
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-ink">Live book</h2>
          <p className="text-sm text-muted">Conviction, weights, horizons</p>
        </div>
        <span className="font-mono text-xs text-muted">{open ? 'Hide' : 'Show'}</span>
      </button>

      {open ? (
        <div className="mt-5 space-y-6">
          <RiskLimitNotice breaches={breaches} />

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="min-w-0">
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                <HintLabel label="Conviction" text={HINTS.conviction} />
              </h3>
              <Suspense fallback={<ChartFallback className="h-64" />}>
                <ConvictionChart conviction={data.conviction} />
              </Suspense>
            </div>
            <div className="min-w-0">
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                <HintLabel label="Weights" text={HINTS.weights} />
              </h3>
              <Suspense fallback={<ChartFallback className="h-64" />}>
                <WeightsChart weights={data.weights} />
              </Suspense>
            </div>
          </div>

          <div className="min-w-0">
            <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
              <HintLabel label="Horizons" text={HINTS.horizonSignals} />
            </h3>
            <HorizonGrid
              tickers={data.tickers}
              horizons={data.horizons}
              signals={data.signals}
            />
          </div>

          <MetaStrip
            portfolioVolatility={data.portfolio_volatility}
            targetVolatility={data.target_volatility}
            volatilities={data.volatilities}
          />
        </div>
      ) : null}
    </section>
  )
}
