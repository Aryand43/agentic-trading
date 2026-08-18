import { Hint, HintLabel } from './Hint'
import { HINTS } from '../content/hints'
import { inactiveHorizons } from '../lib/signals'

type HorizonGridProps = {
  tickers: string[]
  horizons: string[]
  signals: Record<string, Record<string, number>>
}

function cellTone(value: number): string {
  if (value > 0.25) return 'bg-teal-soft/70 text-teal'
  if (value < -0.25) return 'bg-rose-soft/70 text-rose'
  return 'bg-mist text-muted'
}

export function HorizonGrid({ tickers, horizons, signals }: HorizonGridProps) {
  // A column that is exactly zero for every ticker is a strategy that produced
  // nothing, not seven independent neutral readings. Showing it as +0.00 would
  // claim a measurement that was never taken.
  const inactive = inactiveHorizons(signals, horizons)

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-130 border-collapse text-left">
        <thead>
          <tr>
            <th
              scope="col"
              className="pb-3 pr-3 text-xs font-medium uppercase tracking-[0.14em] text-muted"
            >
              Ticker
            </th>
            {horizons.map((h) => (
              <th
                key={h}
                scope="col"
                className="px-1 pb-3 text-center text-xs font-medium uppercase tracking-[0.14em] text-muted"
              >
                <span className="flex flex-col items-center gap-1">
                  <HintLabel
                    label={h}
                    text={HINTS.horizons[h] ?? `${h} holding-period signal (−1 sell … +1 buy).`}
                  />
                  {inactive.has(h) ? (
                    <Hint text={HINTS.horizonInactive} side="bottom">
                      <span className="cursor-help rounded border border-rose/30 bg-rose-soft/40 px-1 py-px font-mono text-[9px] font-medium normal-case tracking-normal text-rose">
                        no signal
                      </span>
                    </Hint>
                  ) : null}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tickers.map((ticker) => (
            <tr key={ticker}>
              <th
                scope="row"
                className="py-1.5 pr-3 text-left font-mono text-sm font-medium text-ink"
              >
                {ticker}
              </th>
              {horizons.map((horizon) => {
                const value = signals[ticker]?.[horizon] ?? 0
                const strategy = HINTS.horizons[horizon] ?? horizon

                if (inactive.has(horizon)) {
                  return (
                    <td key={horizon} className="px-1 py-1.5">
                      <Hint text={HINTS.horizonInactive} side="bottom" className="w-full">
                        <div className="w-full cursor-help rounded-md border border-dashed border-line px-2 py-1.5 text-center font-mono text-xs text-muted/60">
                          —
                        </div>
                      </Hint>
                    </td>
                  )
                }

                return (
                  <td key={horizon} className="px-1 py-1.5">
                    <Hint
                      text={`${ticker} @ ${horizon}: ${value >= 0 ? '+' : ''}${value.toFixed(3)}. ${strategy}`}
                      className="w-full justify-center"
                      side="bottom"
                    >
                      <div
                        className={`w-full cursor-help rounded-md px-2 py-1.5 text-center font-mono text-xs font-medium ${cellTone(value)}`}
                      >
                        {value >= 0 ? '+' : ''}
                        {value.toFixed(2)}
                      </div>
                    </Hint>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
