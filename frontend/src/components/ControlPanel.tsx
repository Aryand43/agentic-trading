import { useState, type ReactNode } from 'react'
import type { RunMode } from '../types/pipeline'
import { HintLabel } from './Hint'
import { HINTS } from '../content/hints'
import { isYearPreset } from '../lib/dates'
import { HORIZONS, NASDAQ_SAMPLE } from '../types/pipeline'

export type ControlPanelProps = {
  mode: RunMode
  onModeChange: (mode: RunMode) => void
  tickersInput: string
  onTickersChange: (v: string) => void
  maxPosition: number
  onMaxPositionChange: (v: number) => void
  grossExposure: number
  onGrossExposureChange: (v: number) => void
  targetVolatility: number
  onTargetVolatilityChange: (v: number) => void
  startDate: string
  endDate: string
  onStartDateChange: (v: string) => void
  onEndDateChange: (v: string) => void
  period: string
  onPeriodChange: (v: string) => void
  useDates: boolean
  onUseDatesChange: (v: boolean) => void
  initialCapital: number
  onInitialCapitalChange: (v: number) => void
  includeBaselines: boolean
  onIncludeBaselinesChange: (v: boolean) => void
  includeSegments: boolean
  onIncludeSegmentsChange: (v: boolean) => void
  horizon: string
  onHorizonChange: (v: string) => void
  iterations: number
  onIterationsChange: (v: number) => void
  loading: boolean
  onRun: () => void
  onApplyPreset: (years: number) => void
}

const MODES: { id: RunMode; label: string }[] = [
  { id: 'backtest', label: 'Backtest' },
  { id: 'live', label: 'Live' },
  { id: 'agent', label: 'Agent' },
]

const field =
  'box-border h-10 w-full min-w-0 max-w-full rounded-md border border-line bg-white px-3 font-mono text-[13px] text-ink outline-none transition placeholder:text-muted/50 focus:border-teal focus:ring-1 focus:ring-teal/40'

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint: string
  children: ReactNode
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <HintLabel
        label={label}
        text={hint}
        className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted"
      />
      {children}
    </div>
  )
}

export function ControlPanel(props: ControlPanelProps) {
  const {
    mode,
    onModeChange,
    tickersInput,
    onTickersChange,
    maxPosition,
    onMaxPositionChange,
    grossExposure,
    onGrossExposureChange,
    targetVolatility,
    onTargetVolatilityChange,
    startDate,
    endDate,
    onStartDateChange,
    onEndDateChange,
    period,
    onPeriodChange,
    useDates,
    onUseDatesChange,
    initialCapital,
    onInitialCapitalChange,
    includeBaselines,
    onIncludeBaselinesChange,
    includeSegments,
    onIncludeSegmentsChange,
    horizon,
    onHorizonChange,
    iterations,
    onIterationsChange,
    loading,
    onRun,
    onApplyPreset,
  } = props

  const [showSizing, setShowSizing] = useState(false)
  const research = mode === 'backtest' || mode === 'agent'

  const cta =
    mode === 'backtest'
      ? loading
        ? 'Running…'
        : 'Run backtest'
      : mode === 'live'
        ? loading
          ? 'Running…'
          : 'Run live snapshot'
        : loading
          ? 'Running…'
          : 'Run discovery'

  return (
    <section className="relative z-10 w-full min-w-0 overflow-visible rounded-xl border border-line bg-white shadow-sm">
      {/* Mode switch */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
        <div
          className="inline-flex max-w-full flex-wrap rounded-lg bg-mist p-0.5"
          role="tablist"
          aria-label="Mode"
        >
          {MODES.map((m) => {
            const active = mode === m.id
            return (
              <button
                key={m.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => onModeChange(m.id)}
                className={[
                  'rounded-md px-3.5 py-1.5 text-sm font-medium transition',
                  active
                    ? 'bg-white text-ink shadow-sm'
                    : 'text-muted hover:text-ink',
                ].join(' ')}
              >
                {m.label}
              </button>
            )
          })}
        </div>
        {research && (
          <div className="flex shrink-0 items-center gap-1">
            {[1, 3, 5].map((y) => {
              const on = useDates && isYearPreset(y, startDate, endDate)
              return (
                <button
                  key={y}
                  type="button"
                  onClick={() => onApplyPreset(y)}
                  className={[
                    'rounded-md px-2.5 py-1 font-mono text-xs transition',
                    on
                      ? 'bg-teal text-fog'
                      : 'bg-mist text-muted hover:text-ink',
                  ].join(' ')}
                >
                  {y}y
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div className="flex min-w-0 flex-col gap-5 px-4 py-4 sm:px-5">
        {research ? (
          <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {useDates ? (
              <>
                <Field label="Start" hint={HINTS.dateStart}>
                  <input
                    type="date"
                    value={startDate}
                    max={endDate}
                    onChange={(e) => onStartDateChange(e.target.value)}
                    className={field}
                  />
                </Field>
                <Field label="End" hint={HINTS.dateEnd}>
                  <input
                    type="date"
                    value={endDate}
                    min={startDate}
                    onChange={(e) => onEndDateChange(e.target.value)}
                    className={field}
                  />
                </Field>
              </>
            ) : (
              <Field label="Period" hint={HINTS.period}>
                <select
                  value={period}
                  onChange={(e) => onPeriodChange(e.target.value)}
                  className={field}
                >
                  {['1y', '2y', '3y', '5y', '10y', 'max'].map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field label="Capital" hint={HINTS.initialCapital}>
              <input
                type="number"
                min={100}
                step={100}
                value={initialCapital}
                onChange={(e) => onInitialCapitalChange(Number(e.target.value))}
                className={field}
              />
            </Field>
            <div className="flex min-w-0 flex-col justify-end gap-1.5">
              <span className="hidden text-[11px] font-medium uppercase tracking-[0.08em] text-transparent lg:block">
                ·
              </span>
              <button
                type="button"
                onClick={() => onUseDatesChange(!useDates)}
                className="h-10 w-full rounded-md border border-line bg-mist/60 text-xs font-medium text-muted transition hover:border-teal hover:text-ink"
              >
                {useDates ? 'Use period string' : 'Use calendar dates'}
              </button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted">
            Snapshot from recent daily history. Use <span className="text-ink">Backtest</span> for
            dated equity curves.
          </p>
        )}

        <Field label="Tickers" hint={HINTS.tickers}>
          <div className="flex min-w-0 flex-col gap-1.5 sm:flex-row sm:items-center">
            <input
              value={tickersInput}
              onChange={(e) => onTickersChange(e.target.value)}
              placeholder="AAPL, MSFT, NVDA"
              className={field}
            />
            <button
              type="button"
              onClick={() => onTickersChange(NASDAQ_SAMPLE)}
              className="shrink-0 text-left text-[11px] font-medium text-teal hover:underline sm:px-2"
            >
              Sample universe
            </button>
          </div>
        </Field>

        {mode === 'agent' && (
          <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Horizon" hint={HINTS.agentHorizon}>
              <select
                value={horizon}
                onChange={(e) => onHorizonChange(e.target.value)}
                className={field}
              >
                {HORIZONS.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Iterations" hint={HINTS.agentIters}>
              <input
                type="number"
                min={1}
                max={5}
                value={iterations}
                onChange={(e) => onIterationsChange(Number(e.target.value))}
                className={field}
              />
            </Field>
          </div>
        )}

        <div className="border-t border-line pt-3">
          <button
            type="button"
            onClick={() => setShowSizing((v) => !v)}
            className="flex w-full items-center justify-between text-left text-xs font-medium text-muted hover:text-ink"
          >
            <span>Sizing & options</span>
            <span className="font-mono">{showSizing ? '−' : '+'}</span>
          </button>
          {showSizing ? (
            <div className="mt-3 grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Max position" hint={HINTS.maxPosition}>
                <input
                  type="number"
                  min={0.01}
                  max={1}
                  step={0.01}
                  value={maxPosition}
                  onChange={(e) => onMaxPositionChange(Number(e.target.value))}
                  className={field}
                />
              </Field>
              <Field label="Gross exposure" hint={HINTS.grossExposure}>
                <input
                  type="number"
                  min={0.01}
                  max={5}
                  step={0.05}
                  value={grossExposure}
                  onChange={(e) => onGrossExposureChange(Number(e.target.value))}
                  className={field}
                />
              </Field>
              <Field label="Target vol" hint={HINTS.targetVol}>
                <input
                  type="number"
                  min={0.01}
                  max={1}
                  step={0.01}
                  value={targetVolatility}
                  onChange={(e) => onTargetVolatilityChange(Number(e.target.value))}
                  className={field}
                />
              </Field>
              {mode === 'backtest' && (
                <div className="flex flex-wrap items-center gap-4 sm:col-span-3">
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={includeBaselines}
                      onChange={(e) => onIncludeBaselinesChange(e.target.checked)}
                      className="accent-teal"
                    />
                    Baselines
                  </label>
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={includeSegments}
                      onChange={(e) => onIncludeSegmentsChange(e.target.checked)}
                      className="accent-teal"
                    />
                    Segments
                  </label>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex flex-col gap-2 border-t border-line bg-fog/50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <p className="order-2 text-xs text-muted sm:order-1">
          {loading
            ? mode === 'agent'
              ? 'Agent loop may take up to a minute…'
              : 'Fetching history & simulating…'
            : mode === 'backtest'
              ? 'Equity curve, baselines, segments'
              : mode === 'live'
                ? 'Current conviction & weights'
                : 'Discover & rank strategies'}
        </p>
        <button
          type="button"
          onClick={onRun}
          disabled={loading}
          className="order-1 inline-flex h-10 min-w-0 items-center justify-center gap-2 rounded-md bg-ink px-5 text-sm font-semibold text-fog transition hover:bg-teal disabled:cursor-not-allowed disabled:opacity-50 sm:order-2 sm:min-w-[9.5rem]"
        >
          {loading ? (
            <span className="size-3.5 animate-spin rounded-full border-2 border-fog/25 border-t-fog" />
          ) : null}
          {cta}
        </button>
      </div>
    </section>
  )
}
