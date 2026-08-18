import { Hint, HintLabel } from './Hint'
import { HINTS } from '../content/hints'
import { fmtNum } from '../lib/format'

type MetaStripProps = {
  portfolioVolatility: number
  targetVolatility: number
  volatilities: Record<string, number>
}

/** Per-ticker vol and portfolio vol arrive on different scales from the API, so
 *  they are grouped separately rather than laid out as directly comparable peers. */
export function MetaStrip({
  portfolioVolatility,
  targetVolatility,
  volatilities,
}: MetaStripProps) {
  return (
    <div className="flex flex-col gap-4 border-t border-line pt-4 sm:flex-row sm:gap-10">
      <div>
        <p className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
          Book level
          <Hint text={HINTS.volScaleMismatch} side="top">
            <span className="cursor-help rounded-full border border-line px-1 font-mono text-[10px] leading-none text-muted">
              ?
            </span>
          </Hint>
        </p>
        <div className="flex gap-8">
          <Metric label="Portfolio vol" value={fmtNum(portfolioVolatility, 4)} hint={HINTS.portfolioVol} />
          <Metric label="Target vol" value={fmtNum(targetVolatility, 4)} hint={HINTS.targetVol} />
        </div>
      </div>

      <div className="min-w-0">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
          Per ticker
        </p>
        <div className="flex flex-wrap gap-x-8 gap-y-3">
          {Object.entries(volatilities).map(([ticker, vol]) => (
            <Metric
              key={ticker}
              label={ticker}
              value={fmtNum(vol, 4)}
              hint={HINTS.tickerVol(ticker)}
            />
          ))}
        </div>
      </div>
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
