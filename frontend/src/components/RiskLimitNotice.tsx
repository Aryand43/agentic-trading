import { HINTS } from '../content/hints'
import { fmtNum, fmtPct } from '../lib/format'
import type { LimitBreach } from '../lib/limits'
import { Hint } from './Hint'

const LABEL: Record<LimitBreach['kind'], string> = {
  max_position: 'Max position',
  gross_exposure: 'Gross exposure',
}

/** Shown when the weights we got back exceed the limits we sent.
 *  The desk has both numbers, so it verifies rather than assumes. */
export function RiskLimitNotice({ breaches }: { breaches: LimitBreach[] }) {
  if (!breaches.length) return null

  return (
    <div
      role="status"
      className="rounded-lg border border-rose/25 bg-rose-soft/30 px-4 py-3 text-sm"
    >
      <p className="font-medium text-ink">
        This book exceeds the limits you set{' '}
        <Hint text={HINTS.limitBreach} side="bottom">
          <span className="cursor-help rounded-full border border-rose/40 px-1 font-mono text-[10px] leading-none text-rose">
            ?
          </span>
        </Hint>
      </p>
      <ul className="mt-2 space-y-1 font-mono text-[12px] tabular-nums text-ink">
        {breaches.map((b) => (
          <li key={b.kind} className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-sans text-muted">{LABEL[b.kind]}</span>
            <span className="text-muted">requested</span>
            <span>{fmtNum(b.requested, 2)}</span>
            <span className="text-line">→</span>
            <span className="text-muted">returned</span>
            <span className="font-semibold text-rose">
              {fmtNum(b.actual, 3)}
              {b.ticker ? <span className="ml-1 font-sans font-normal">({b.ticker})</span> : null}
            </span>
            <span className="text-muted">
              — {fmtNum(b.ratio, 1)}× over ({fmtPct(b.actual - b.requested, 1)} above the cap)
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted">
        Weights below are shown as returned. Treat the sizing as unenforced until this is fixed
        upstream.
      </p>
    </div>
  )
}
