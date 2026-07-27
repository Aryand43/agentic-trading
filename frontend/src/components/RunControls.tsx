import { Hint, HintLabel } from './Hint'
import { HINTS } from '../content/hints'

type RunControlsProps = {
  tickersInput: string
  maxPosition: number
  loading: boolean
  onTickersChange: (value: string) => void
  onMaxPositionChange: (value: number) => void
  onRun: () => void
}

export function RunControls({
  tickersInput,
  maxPosition,
  loading,
  onTickersChange,
  onMaxPositionChange,
  onRun,
}: RunControlsProps) {
  return (
    <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="flex flex-1 flex-col gap-4 sm:flex-row">
        <label className="flex min-w-0 flex-1 flex-col gap-1.5">
          <HintLabel
            label="Tickers"
            text={HINTS.tickers}
            className="text-xs font-medium uppercase tracking-[0.14em] text-muted"
          />
          <input
            value={tickersInput}
            onChange={(e) => onTickersChange(e.target.value)}
            placeholder="AAPL, MSFT, NVDA"
            className="rounded-lg border border-line bg-white/80 px-3 py-2.5 font-mono text-sm outline-none ring-teal/30 transition focus:ring-2"
          />
        </label>
        <label className="flex w-full flex-col gap-1.5 sm:w-40">
          <HintLabel
            label="Max position"
            text={HINTS.maxPosition}
            className="text-xs font-medium uppercase tracking-[0.14em] text-muted"
          />
          <input
            type="number"
            min={0.01}
            max={1}
            step={0.01}
            value={maxPosition}
            onChange={(e) => onMaxPositionChange(Number(e.target.value))}
            className="rounded-lg border border-line bg-white/80 px-3 py-2.5 font-mono text-sm outline-none ring-teal/30 transition focus:ring-2"
          />
        </label>
      </div>
      <Hint text={HINTS.runPipeline}>
        <button
          type="button"
          onClick={onRun}
          disabled={loading}
          className="rounded-lg bg-ink px-5 py-2.5 text-sm font-semibold text-fog transition hover:bg-teal disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? 'Running pipeline…' : 'Run pipeline'}
        </button>
      </Hint>
    </section>
  )
}
