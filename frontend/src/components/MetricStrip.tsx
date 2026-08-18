import { HintLabel } from './Hint'

export type Tone = 'up' | 'down' | 'flat'

const TONE_CLASS: Record<Tone, string> = {
  up: 'text-teal',
  down: 'text-rose',
  flat: 'text-ink',
}

export type MetricCellSpec = {
  label: string
  value: string
  /** Omit to render in the neutral ink colour. */
  tone?: Tone
  /** Optional hover explanation for the label. */
  hint?: string
}

export function MetricStrip({ cells }: { cells: MetricCellSpec[] }) {
  return (
    <div className="grid min-w-0 grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-5">
      {cells.map((c) => (
        <div key={c.label} className="bg-white/90 px-3 py-3 sm:px-4">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted">
            {c.hint ? <HintLabel label={c.label} text={c.hint} side="bottom" /> : c.label}
          </p>
          <p
            className={`mt-0.5 font-mono text-lg font-semibold tabular-nums ${TONE_CLASS[c.tone ?? 'flat']}`}
          >
            {c.value}
          </p>
        </div>
      ))}
    </div>
  )
}
