import { Suspense, lazy } from 'react'
import { HintLabel } from './Hint'
import { HINTS } from '../content/hints'
import { MetricStrip } from './MetricStrip'
import { SegmentReport } from './SegmentReport'
import { ChartFallback } from './ChartFallback'
import { fmtNum, fmtPct, humanize } from '../lib/format'
import type { BacktestResult } from '../types/pipeline'

const EquityChart = lazy(() =>
  import('./EquityChart').then((m) => ({ default: m.EquityChart })),
)

export function BacktestPanel({ data }: { data: BacktestResult }) {
  const { window, metrics, research_windows: rw } = data
  const hit = metrics.signal_hit_rate ?? metrics.hit_rate

  return (
    <>
      <section className="relative z-0 min-w-0 space-y-5 animate-[fadeIn_0.35s_ease-out]">
        <div className="space-y-1">
          <p className="font-mono text-xs text-muted">
            <span className="text-ink">
              {window.start}
              <span className="mx-1.5 text-line">→</span>
              {window.end}
            </span>
            <span className="mx-2 text-line">·</span>
            {window.n_days} trading days
            <span className="mx-2 text-line">·</span>${data.initial_capital.toLocaleString()}
            <span className="mx-2 text-line">·</span>
            {data.tickers.join(', ')}
          </p>
          {rw?.train ? (
            <p className="font-mono text-[11px] text-muted">
              <span className="text-muted">Train </span>
              <span className="text-ink">
                {rw.train.start}→{rw.train.end}
              </span>
              <span className="mx-1.5 text-line">·</span>
              <span className="text-muted">Val </span>
              <span className="text-ink">
                {rw.val?.start}→{rw.val?.end}
              </span>
              <span className="mx-1.5 text-line">·</span>
              <span className="text-muted">Test </span>
              <span className="text-ink">
                {rw.test?.start}→{rw.test?.end}
              </span>
            </p>
          ) : null}
        </div>

        <div>
          <h2 className="text-lg font-semibold tracking-tight text-ink">
            <HintLabel label="Capital" text={HINTS.equityCurve} />
          </h2>
          <p className="mt-0.5 text-sm text-muted">Multi-horizon book vs baselines</p>
        </div>

        <MetricStrip
          cells={[
            { label: 'Sharpe', value: fmtNum(metrics.sharpe), hint: HINTS.sharpe },
            {
              label: 'ARR',
              value: fmtPct(metrics.annualized_return),
              tone: metrics.annualized_return >= 0 ? 'up' : 'down',
            },
            { label: 'Max DD', value: fmtPct(metrics.max_drawdown), tone: 'down' },
            { label: 'Hit', value: fmtPct(hit), hint: HINTS.hitRate },
            { label: 'Utility', value: fmtNum(metrics.utility ?? 0) },
          ]}
        />

        <div className="min-w-0 overflow-hidden rounded-lg border border-line bg-white/80 p-3 sm:p-4">
          <Suspense fallback={<ChartFallback />}>
            <EquityChart
              equityCurve={data.equity_curve}
              baselineCurves={data.baseline_curves}
              initialCapital={data.initial_capital}
            />
          </Suspense>
        </div>

        {Object.keys(data.baselines).length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
                  <th scope="col" className="pb-2 pr-4 font-medium">
                    Series
                  </th>
                  <th scope="col" className="pb-2 pr-4 text-right font-medium">
                    Sharpe
                  </th>
                  <th scope="col" className="pb-2 pr-4 text-right font-medium">
                    Return
                  </th>
                  <th scope="col" className="pb-2 text-right font-medium">
                    Max DD
                  </th>
                </tr>
              </thead>
              <tbody className="font-mono text-[13px] tabular-nums">
                <tr className="border-b border-line/70">
                  <th scope="row" className="py-2.5 pr-4 text-left font-sans font-medium">
                    Strategy
                  </th>
                  <td className="py-2.5 pr-4 text-right">{fmtNum(metrics.sharpe)}</td>
                  <td className="py-2.5 pr-4 text-right">{fmtPct(metrics.total_return)}</td>
                  <td className="py-2.5 text-right">{fmtPct(metrics.max_drawdown)}</td>
                </tr>
                {Object.entries(data.baselines).map(([name, m]) => (
                  <tr key={name} className="border-b border-line/70 last:border-0">
                    <th scope="row" className="py-2.5 pr-4 text-left font-sans font-medium">
                      {humanize(name)}
                    </th>
                    <td className="py-2.5 pr-4 text-right">{fmtNum(m.sharpe)}</td>
                    <td className="py-2.5 pr-4 text-right">{fmtPct(m.total_return)}</td>
                    <td className="py-2.5 text-right">{fmtPct(m.max_drawdown)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {data.segments && Object.keys(data.segments).length > 0 ? (
        <section className="space-y-4 border-t border-line pt-6 animate-[fadeIn_0.35s_ease-out]">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-ink">
              <HintLabel label="Segments" text={HINTS.segments} />
            </h2>
          </div>
          <SegmentReport segments={data.segments} />
        </section>
      ) : null}
    </>
  )
}
