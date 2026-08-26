import { useMemo, useState } from 'react'
import { AgentHistory } from './components/AgentHistory'
import { ControlPanel } from './components/ControlPanel'
import { ConvictionChart } from './components/ConvictionChart'
import { EquityChart } from './components/EquityChart'
import { HintLabel } from './components/Hint'
import { HorizonGrid } from './components/HorizonGrid'
import { MetaStrip } from './components/MetaStrip'
import { RiskComparisonTable } from './components/RiskComparisonTable'
import { SegmentReport } from './components/SegmentReport'
import { TradeAuditTable } from './components/TradeAuditTable'
import { WeightsChart } from './components/WeightsChart'
import { HINTS } from './content/hints'
import { useAgent, useBacktest, usePipeline } from './hooks/usePipeline'
import { todayYMD, yearsAgoYMD } from './lib/dates'
import { DESK_VERSION, formatDeskError } from './lib/errors'
import type { RunMode, WindowInfo } from './types/pipeline'

function parseTickers(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
}

function fmtPct(x: number): string {
  return `${(x * 100).toFixed(1)}%`
}

export default function App() {
  const pipeline = usePipeline()
  const backtest = useBacktest()
  const agent = useAgent()

  const [mode, setMode] = useState<RunMode>('backtest')
  const [tickersInput, setTickersInput] = useState('AAPL, MSFT, NVDA')
  const [maxPosition, setMaxPosition] = useState(0.15)
  const [grossExposure, setGrossExposure] = useState(1.0)
  const [targetVolatility, setTargetVolatility] = useState(0.15)
  const [useDates, setUseDates] = useState(true)
  const [startDate, setStartDate] = useState(() => yearsAgoYMD(3))
  const [endDate, setEndDate] = useState(() => todayYMD())
  const [period, setPeriod] = useState('3y')
  const [initialCapital, setInitialCapital] = useState(10_000)
  const [includeBaselines, setIncludeBaselines] = useState(true)
  const [includeSegments, setIncludeSegments] = useState(true)
  const [horizon, setHorizon] = useState('10d')
  const [iterations, setIterations] = useState(2)
  const [liveOpen, setLiveOpen] = useState(true)

  const loading = pipeline.loading || backtest.loading || agent.loading
  const error = formatDeskError(pipeline.error || backtest.error || agent.error)

  const tickersOrNull = () => {
    const parsed = parseTickers(tickersInput)
    return parsed.length ? parsed : null
  }

  const windowFields = () =>
    useDates
      ? { start_date: startDate, end_date: endDate, period: period || '3y' }
      : { start_date: null, end_date: null, period }

  const applyPreset = (years: number) => {
    setUseDates(true)
    setStartDate(yearsAgoYMD(years))
    setEndDate(todayYMD())
    setPeriod(`${years}y`)
  }

  const snapFormToWindow = (window: WindowInfo) => {
    setUseDates(true)
    setStartDate(window.start)
    setEndDate(window.end)
  }

  const handleRun = async () => {
    const tickers = tickersOrNull()
    if (mode === 'live') {
      await pipeline.run({
        tickers,
        max_position: maxPosition,
        gross_exposure: grossExposure,
        target_volatility: targetVolatility,
      })
      setLiveOpen(true)
      return
    }
    if (mode === 'backtest') {
      const result = await backtest.run({
        tickers,
        ...windowFields(),
        initial_capital: initialCapital,
        max_position: maxPosition,
        gross_exposure: grossExposure,
        target_volatility: targetVolatility,
        include_baselines: includeBaselines,
        include_segments: includeSegments,
      })
      if (result?.window) snapFormToWindow(result.window)
      return
    }
    const result = await agent.run({
      tickers,
      ...windowFields(),
      horizon,
      n_iterations: iterations,
      initial_capital: initialCapital,
    })
    if (result?.window) snapFormToWindow(result.window)
  }

  const activeWindow: WindowInfo | null = useMemo(() => {
    if (backtest.data?.window) return backtest.data.window
    if (agent.data?.window) return agent.data.window
    return null
  }, [backtest.data, agent.data])

  const hasResults = Boolean(backtest.data || agent.data || pipeline.data)

  return (
    <div className="relative isolate mx-auto flex min-h-screen w-full max-w-3xl min-w-0 flex-col gap-8 px-4 py-8 sm:max-w-5xl sm:px-6 sm:py-10 lg:max-w-6xl">
      {/* Brand bar — tight */}
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-line/80 pb-5">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-teal">
            Agentic Trading
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            Research desk
          </h1>
        </div>
        <p className="font-mono text-[11px] text-muted">{DESK_VERSION}</p>
      </header>

      <ControlPanel
        mode={mode}
        onModeChange={setMode}
        tickersInput={tickersInput}
        onTickersChange={setTickersInput}
        maxPosition={maxPosition}
        onMaxPositionChange={setMaxPosition}
        grossExposure={grossExposure}
        onGrossExposureChange={setGrossExposure}
        targetVolatility={targetVolatility}
        onTargetVolatilityChange={setTargetVolatility}
        startDate={startDate}
        endDate={endDate}
        onStartDateChange={setStartDate}
        onEndDateChange={setEndDate}
        period={period}
        onPeriodChange={setPeriod}
        useDates={useDates}
        onUseDatesChange={setUseDates}
        initialCapital={initialCapital}
        onInitialCapitalChange={setInitialCapital}
        includeBaselines={includeBaselines}
        onIncludeBaselinesChange={setIncludeBaselines}
        includeSegments={includeSegments}
        onIncludeSegmentsChange={setIncludeSegments}
        horizon={horizon}
        onHorizonChange={setHorizon}
        iterations={iterations}
        onIterationsChange={setIterations}
        loading={loading}
        onRun={handleRun}
        onApplyPreset={applyPreset}
      />

      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-rose/20 bg-rose-soft/40 px-4 py-3 text-sm animate-[fadeIn_0.25s_ease-out]"
        >
          <p className="font-medium text-ink">Run failed</p>
          <p className="mt-0.5 text-rose/95">{error}</p>
        </div>
      ) : null}

      {!hasResults && !loading ? (
        <p className="text-center text-sm text-muted">
          Choose a window, then run a <span className="text-ink">backtest</span>.
        </p>
      ) : null}

      {backtest.data ? (
        <section className="relative z-0 min-w-0 space-y-5 animate-[fadeIn_0.35s_ease-out]">
          {activeWindow ? (
            <div className="space-y-1">
              <p className="font-mono text-xs text-muted">
                <span className="text-ink">
                  {activeWindow.start}
                  <span className="mx-1.5 text-line">→</span>
                  {activeWindow.end}
                </span>
                <span className="mx-2 text-line">·</span>
                {activeWindow.n_days} trading days
                {activeWindow.n_days < 120 ? (
                  <span className="ml-2 text-rose">low sample</span>
                ) : null}
                <span className="mx-2 text-line">·</span>$
                {backtest.data.initial_capital.toLocaleString()}
                <span className="mx-2 text-line">·</span>
                {backtest.data.tickers.join(', ')}
              </p>
              {backtest.data.research_windows?.train ? (
                <p className="font-mono text-[11px] text-muted">
                  <span className="text-muted">Train </span>
                  <span className="text-ink">
                    {backtest.data.research_windows.train.start}→
                    {backtest.data.research_windows.train.end}
                  </span>
                  <span className="mx-1.5 text-line">·</span>
                  <span className="text-muted">Val </span>
                  <span className="text-ink">
                    {backtest.data.research_windows.val?.start}→
                    {backtest.data.research_windows.val?.end}
                  </span>
                  <span className="mx-1.5 text-line">·</span>
                  <span className="text-muted">Test </span>
                  <span className="text-ink">
                    {backtest.data.research_windows.test?.start}→
                    {backtest.data.research_windows.test?.end}
                  </span>
                </p>
              ) : null}
            </div>
          ) : null}

          <div>
            <h2 className="text-lg font-semibold tracking-tight text-ink">
              <HintLabel label="Capital" text={HINTS.equityCurve} />
            </h2>
            <p className="mt-0.5 text-sm text-muted">Multi-horizon book vs baselines</p>
          </div>

          <div className="grid min-w-0 grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-5">
            <MetricCell label="Sharpe" value={backtest.data.metrics.sharpe.toFixed(2)} />
            <MetricCell
              label="ARR"
              value={fmtPct(backtest.data.metrics.annualized_return)}
              tone={backtest.data.metrics.annualized_return >= 0 ? 'up' : 'down'}
            />
            <MetricCell
              label="Max DD"
              value={fmtPct(backtest.data.metrics.max_drawdown)}
              tone="down"
            />
            <MetricCell
              label="Hit"
              value={fmtPct(
                backtest.data.metrics.signal_hit_rate ?? backtest.data.metrics.hit_rate,
              )}
            />
            <MetricCell
              label="Utility"
              value={(backtest.data.metrics.utility ?? 0).toFixed(2)}
            />
          </div>

          <div className="min-w-0 overflow-hidden rounded-lg border border-line bg-white/80 p-3 sm:p-4">
            <EquityChart
              equityCurve={backtest.data.equity_curve}
              baselineCurves={backtest.data.baseline_curves}
              initialCapital={backtest.data.initial_capital}
              trades={backtest.data.trades}
            />
          </div>

          {Object.keys(backtest.data.baselines).length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
                    <th className="pb-2 pr-4 font-medium">Series</th>
                    <th className="pb-2 pr-4 font-medium">Sharpe</th>
                    <th className="pb-2 pr-4 font-medium">Return</th>
                    <th className="pb-2 font-medium">Max DD</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-[13px]">
                  <tr className="border-b border-line/70">
                    <td className="py-2.5 pr-4 font-sans font-medium">Strategy</td>
                    <td className="py-2.5 pr-4">{backtest.data.metrics.sharpe.toFixed(2)}</td>
                    <td className="py-2.5 pr-4">{fmtPct(backtest.data.metrics.total_return)}</td>
                    <td className="py-2.5">{fmtPct(backtest.data.metrics.max_drawdown)}</td>
                  </tr>
                  {Object.entries(backtest.data.baselines).map(([name, m]) => (
                    <tr key={name} className="border-b border-line/70 last:border-0">
                      <td className="py-2.5 pr-4 font-sans font-medium capitalize">
                        {name.replace(/_/g, ' ')}
                      </td>
                      <td className="py-2.5 pr-4">{m.sharpe.toFixed(2)}</td>
                      <td className="py-2.5 pr-4">{fmtPct(m.total_return)}</td>
                      <td className="py-2.5">{fmtPct(m.max_drawdown)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      ) : null}

      {backtest.data?.trades && backtest.data.trades.length > 0 ? (
        <section className="space-y-3 border-t border-line pt-6 animate-[fadeIn_0.35s_ease-out]">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-ink">
              <HintLabel label="Trade audit" text={HINTS.tradeAudit} />
            </h2>
            <p className="mt-0.5 text-sm text-muted">Every fill, exit reason, and PnL</p>
          </div>
          <TradeAuditTable
            trades={backtest.data.trades}
            signalEvents={backtest.data.signal_events}
            truncated={backtest.data.trades_truncated}
          />
        </section>
      ) : null}

      {backtest.data?.risk_comparison && backtest.data.risk_comparison.length > 0 ? (
        <section className="space-y-3 border-t border-line pt-6 animate-[fadeIn_0.35s_ease-out]">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-ink">
              <HintLabel label="Risk comparison" text={HINTS.riskComparison} />
            </h2>
            <p className="mt-0.5 text-sm text-muted">
              Predicted vs realized — no method is ranked without these numbers
            </p>
          </div>
          <RiskComparisonTable rows={backtest.data.risk_comparison} />
        </section>
      ) : null}

      {backtest.data?.segments && Object.keys(backtest.data.segments).length > 0 ? (
        <section className="space-y-3 border-t border-line pt-6 animate-[fadeIn_0.35s_ease-out]">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-ink">
              <HintLabel label="Segments" text={HINTS.segments} />
            </h2>
            <p className="mt-0.5 text-sm text-muted">Regime, volatility, industry</p>
          </div>
          <SegmentReport segments={backtest.data.segments} />
        </section>
      ) : null}

      {agent.data ? (
        <section className="space-y-3 border-t border-line pt-6 animate-[fadeIn_0.35s_ease-out]">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-ink">
              <HintLabel label="Agent" text={HINTS.agentHistory} />
            </h2>
            <p className="mt-0.5 text-sm text-muted">Iterations by out-of-sample utility</p>
          </div>
          <AgentHistory data={agent.data} />
        </section>
      ) : null}

      {pipeline.data ? (
        <section className="border-t border-line pt-6 animate-[fadeIn_0.35s_ease-out]">
          <button
            type="button"
            onClick={() => setLiveOpen((o) => !o)}
            className="flex w-full items-baseline justify-between gap-3 text-left"
          >
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-ink">Live book</h2>
              <p className="text-sm text-muted">Conviction, weights, horizons</p>
            </div>
            <span className="font-mono text-xs text-muted">{liveOpen ? 'Hide' : 'Show'}</span>
          </button>
          {liveOpen ? (
            <div className="mt-5 space-y-6">
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                    <HintLabel label="Conviction" text={HINTS.conviction} />
                  </h3>
                  <ConvictionChart conviction={pipeline.data.conviction} />
                </div>
                <div>
                  <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                    <HintLabel label="Weights" text={HINTS.weights} />
                  </h3>
                  <WeightsChart weights={pipeline.data.weights} />
                </div>
              </div>
              <div>
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                  <HintLabel label="Horizons" text={HINTS.horizonSignals} />
                </h3>
                <HorizonGrid
                  tickers={pipeline.data.tickers}
                  horizons={pipeline.data.horizons}
                  signals={pipeline.data.signals}
                />
              </div>
              <MetaStrip
                portfolioVolatility={pipeline.data.portfolio_volatility}
                targetVolatility={pipeline.data.target_volatility}
                volatilities={pipeline.data.volatilities}
              />
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}

function MetricCell({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: 'up' | 'down'
}) {
  const toneClass =
    tone === 'up' ? 'text-teal' : tone === 'down' ? 'text-rose' : 'text-ink'
  return (
    <div className="bg-white/90 px-3 py-3 sm:px-4">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-0.5 font-mono text-lg font-semibold tabular-nums ${toneClass}`}>{value}</p>
    </div>
  )
}
