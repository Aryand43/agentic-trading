import { HintLabel } from './Hint'
import { HINTS } from '../content/hints'

type MetaStripProps = {
  portfolioVolatility: number
  targetVolatility: number
  volatilities: Record<string, number>
}

export function MetaStrip({
  portfolioVolatility,
  targetVolatility,
  volatilities,
}: MetaStripProps) {
  return (
    <div className="flex flex-wrap gap-x-8 gap-y-3 border-t border-line pt-4">
      <Metric label="Portfolio vol" value={portfolioVolatility.toFixed(4)} hint={HINTS.portfolioVol} />
      <Metric label="Target vol" value={targetVolatility.toFixed(4)} hint={HINTS.targetVol} />
      {Object.entries(volatilities).map(([ticker, vol]) => (
        <Metric
          key={ticker}
          label={`${ticker} vol`}
          value={vol.toFixed(4)}
          hint={HINTS.tickerVol(ticker)}
        />
      ))}
    </div>
  )
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div>
      <HintLabel
        label={label}
        text={hint}
        className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted"
      />
      <div className="mt-0.5 font-mono text-sm font-medium tabular-nums">{value}</div>
    </div>
  )
}
