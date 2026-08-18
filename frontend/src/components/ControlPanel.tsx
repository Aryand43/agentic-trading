import { useId, useState, type ReactNode } from 'react'
import type { RunMode } from '../types/pipeline'
import { Hint } from './Hint'
import { HINTS } from '../content/hints'
import { isYearPreset } from '../lib/dates'
import { HORIZONS, NASDAQ_SAMPLE } from '../types/pipeline'
import type { DeskParams } from '../state/deskParams'

export type ControlPanelProps = {
  params: DeskParams
  /** Patch any subset of the form state. */
  onChange: (patch: Partial<DeskParams>) => void
  onApplyPreset: (years: number) => void
  loading: boolean
  onRun: () => void
  /** Abort the in-flight run. */
  onCancel: () => void
}

const MODES: { id: RunMode; label: string }[] = [
  { id: 'backtest', label: 'Backtest' },
  { id: 'live', label: 'Live' },
  { id: 'agent', label: 'Agent' },
]

const CTA: Record<RunMode, string> = {
  backtest: 'Run backtest',
  live: 'Run live snapshot',
  agent: 'Run discovery',
}

const FOOTNOTE: Record<RunMode, string> = {
  backtest: 'Equity curve, baselines, segments',
  live: 'Current conviction & weights',
  agent: 'Discover & rank strategies',
}

const field =
  'box-border h-10 w-full min-w-0 max-w-full rounded-md border border-line bg-white px-3 font-mono text-[13px] text-ink outline-none transition placeholder:text-muted/50 focus:border-teal focus:ring-1 focus:ring-teal/40'

/** Props a Field hands to its control so the pairing is programmatic, not visual. */
type ControlIds = { id: string; 'aria-describedby': string }

/** Labelled form row.
 *
 * The control is passed the `id`/`aria-describedby` to spread, rather than the
 * label being a bare <span> next to it — an unassociated label leaves the input
 * with no accessible name at all. A render prop is used instead of implicit
 * <label> wrapping because some rows (Tickers) also contain a button, which
 * must not become part of the label's click target.
 */
function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint: string
  children: (ids: ControlIds) => ReactNode
}) {
  const id = useId()
  const descId = `${id}-desc`

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Hint text={hint}>
        <label
          htmlFor={id}
          className="cursor-help border-b border-dotted border-muted/50 text-[11px] font-medium uppercase tracking-[0.08em] text-muted"
        >
          {label}
        </label>
      </Hint>
      {/* Sighted users get the hint on hover; this carries it to screen readers. */}
      <span id={descId} className="sr-only">
        {hint}
      </span>
      {children({ id, 'aria-describedby': descId })}
    </div>
  )
}

export function ControlPanel({
  params,
  onChange,
  onApplyPreset,
  loading,
  onRun,
  onCancel,
}: ControlPanelProps) {
  const [showSizing, setShowSizing] = useState(false)
  const { mode } = params
  const research = mode === 'backtest' || mode === 'agent'

  return (
    <section
      aria-label="Run controls"
      className="relative z-10 w-full min-w-0 overflow-visible rounded-xl border border-line bg-white shadow-sm"
    >
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
                onClick={() => onChange({ mode: m.id })}
                className={[
                  'rounded-md px-3.5 py-1.5 text-sm font-medium transition',
                  active ? 'bg-white text-ink shadow-sm' : 'text-muted hover:text-ink',
                ].join(' ')}
              >
                {m.label}
              </button>
            )
          })}
        </div>
        {research && (
          <div className="flex shrink-0 items-center gap-1" role="group" aria-label="Window preset">
            {[1, 3, 5].map((y) => {
              const on = params.useDates && isYearPreset(y, params.startDate, params.endDate)
              return (
                <button
                  key={y}
                  type="button"
                  aria-pressed={on}
                  onClick={() => onApplyPreset(y)}
                  className={[
                    'rounded-md px-2.5 py-1 font-mono text-xs transition',
                    on ? 'bg-teal text-fog' : 'bg-mist text-muted hover:text-ink',
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
            {params.useDates ? (
              <>
                <Field label="Start" hint={HINTS.dateStart}>
                  {(ids) => (
                    <input
                      {...ids}
                      type="date"
                      value={params.startDate}
                      max={params.endDate}
                      onChange={(e) => onChange({ startDate: e.target.value })}
                      className={field}
                    />
                  )}
                </Field>
                <Field label="End" hint={HINTS.dateEnd}>
                  {(ids) => (
                    <input
                      {...ids}
                      type="date"
                      value={params.endDate}
                      min={params.startDate}
                      onChange={(e) => onChange({ endDate: e.target.value })}
                      className={field}
                    />
                  )}
                </Field>
              </>
            ) : (
              <Field label="Period" hint={HINTS.period}>
                {(ids) => (
                  <select
                    {...ids}
                    value={params.period}
                    onChange={(e) => onChange({ period: e.target.value })}
                    className={field}
                  >
                    {['1y', '2y', '3y', '5y', '10y', 'max'].map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            )}
            <Field label="Capital" hint={HINTS.initialCapital}>
              {(ids) => (
                <input
                  {...ids}
                  type="number"
                  min={100}
                  step={100}
                  value={params.initialCapital}
                  onChange={(e) => onChange({ initialCapital: Number(e.target.value) })}
                  className={field}
                />
              )}
            </Field>
            <div className="flex min-w-0 flex-col justify-end gap-1.5">
              <span
                aria-hidden
                className="hidden text-[11px] font-medium uppercase tracking-[0.08em] text-transparent lg:block"
              >
                ·
              </span>
              <button
                type="button"
                onClick={() => onChange({ useDates: !params.useDates })}
                className="h-10 w-full rounded-md border border-line bg-mist/60 text-xs font-medium text-muted transition hover:border-teal hover:text-ink"
              >
                {params.useDates ? 'Use period string' : 'Use calendar dates'}
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
          {(ids) => (
            <div className="flex min-w-0 flex-col gap-1.5 sm:flex-row sm:items-center">
              <input
                {...ids}
                value={params.tickersInput}
                onChange={(e) => onChange({ tickersInput: e.target.value })}
                placeholder="AAPL, MSFT, NVDA"
                className={field}
              />
              <button
                type="button"
                onClick={() => onChange({ tickersInput: NASDAQ_SAMPLE })}
                className="shrink-0 text-left text-[11px] font-medium text-teal hover:underline sm:px-2"
              >
                Sample universe
              </button>
            </div>
          )}
        </Field>

        {mode === 'agent' && (
          <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Horizon" hint={HINTS.agentHorizon}>
              {(ids) => (
                <select
                  {...ids}
                  value={params.horizon}
                  onChange={(e) => onChange({ horizon: e.target.value })}
                  className={field}
                >
                  {HORIZONS.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Iterations" hint={HINTS.agentIters}>
              {(ids) => (
                <input
                  {...ids}
                  type="number"
                  min={1}
                  max={5}
                  value={params.iterations}
                  onChange={(e) => onChange({ iterations: Number(e.target.value) })}
                  className={field}
                />
              )}
            </Field>
          </div>
        )}

        <div className="border-t border-line pt-3">
          <button
            type="button"
            onClick={() => setShowSizing((v) => !v)}
            aria-expanded={showSizing}
            className="flex w-full items-center justify-between text-left text-xs font-medium text-muted hover:text-ink"
          >
            <span>Sizing &amp; options</span>
            <span aria-hidden className="font-mono">
              {showSizing ? '−' : '+'}
            </span>
          </button>
          {showSizing ? (
            <div className="mt-3 grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Max position" hint={HINTS.maxPosition}>
                {(ids) => (
                  <input
                    {...ids}
                    type="number"
                    min={0.01}
                    max={1}
                    step={0.01}
                    value={params.maxPosition}
                    onChange={(e) => onChange({ maxPosition: Number(e.target.value) })}
                    className={field}
                  />
                )}
              </Field>
              <Field label="Gross exposure" hint={HINTS.grossExposure}>
                {(ids) => (
                  <input
                    {...ids}
                    type="number"
                    min={0.01}
                    max={5}
                    step={0.05}
                    value={params.grossExposure}
                    onChange={(e) => onChange({ grossExposure: Number(e.target.value) })}
                    className={field}
                  />
                )}
              </Field>
              <Field label="Target vol" hint={HINTS.targetVol}>
                {(ids) => (
                  <input
                    {...ids}
                    type="number"
                    min={0.01}
                    max={1}
                    step={0.01}
                    value={params.targetVolatility}
                    onChange={(e) => onChange({ targetVolatility: Number(e.target.value) })}
                    className={field}
                  />
                )}
              </Field>
              {mode === 'backtest' && (
                <div className="flex flex-wrap items-center gap-4 sm:col-span-3">
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={params.includeBaselines}
                      onChange={(e) => onChange({ includeBaselines: e.target.checked })}
                      className="accent-teal"
                    />
                    Baselines
                  </label>
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={params.includeSegments}
                      onChange={(e) => onChange({ includeSegments: e.target.checked })}
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
        <p className="order-2 text-xs text-muted sm:order-1" aria-live="polite">
          {loading
            ? mode === 'agent'
              ? 'Agent loop may take up to a minute…'
              : 'Fetching history & simulating…'
            : FOOTNOTE[mode]}
        </p>
        <div className="order-1 flex items-center gap-2 sm:order-2">
          {loading ? (
            <button
              type="button"
              onClick={onCancel}
              className="h-10 shrink-0 rounded-md border border-line bg-white px-4 text-sm font-medium text-muted transition hover:border-rose hover:text-rose"
            >
              Cancel
            </button>
          ) : null}
          <button
            type="button"
            onClick={onRun}
            disabled={loading}
            className="inline-flex h-10 min-w-0 items-center justify-center gap-2 rounded-md bg-ink px-5 text-sm font-semibold text-fog transition hover:bg-teal disabled:cursor-not-allowed disabled:opacity-50 sm:min-w-38"
          >
            {loading ? (
              <span
                aria-hidden
                className="size-3.5 animate-spin rounded-full border-2 border-fog/25 border-t-fog"
              />
            ) : null}
            {loading ? 'Running…' : CTA[mode]}
          </button>
        </div>
      </div>
    </section>
  )
}
