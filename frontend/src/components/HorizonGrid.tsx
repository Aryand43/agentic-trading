import { Hint, HintLabel } from './Hint'
import { HINTS } from '../content/hints'

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
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] border-collapse text-left">
        <thead>
          <tr>
            <th className="pb-3 pr-3 text-xs font-medium uppercase tracking-[0.14em] text-muted">
              Ticker
            </th>
            {horizons.map((h) => (
              <th
                key={h}
                className="pb-3 px-1 text-center text-xs font-medium uppercase tracking-[0.14em] text-muted"
              >
                <HintLabel
                  label={h}
                  text={HINTS.horizons[h] ?? `${h} holding-period signal (−1 sell … +1 buy).`}
                />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tickers.map((ticker) => (
            <tr key={ticker}>
              <td className="py-1.5 pr-3 font-mono text-sm font-medium">{ticker}</td>
              {horizons.map((horizon) => {
                const value = signals[ticker]?.[horizon] ?? 0
                const strategy = HINTS.horizons[horizon] ?? horizon
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
