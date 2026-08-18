import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { EquityPoint } from '../types/pipeline'
import { detectWarmup } from '../lib/equity'
import { fmtPct } from '../lib/format'

const SERIES_COLORS: Record<string, string> = {
  strategy: '#0f766e',
  buy_and_hold: '#78716c',
  sma_cross: '#c2410c',
  rsi_mean_reversion: '#57534e',
  momentum_20d: '#0e7490',
}

type Props = {
  equityCurve: EquityPoint[]
  baselineCurves?: Record<string, EquityPoint[]>
}

export function EquityChart({ equityCurve, baselineCurves = {} }: Props) {
  const byDate = new Map<string, Record<string, number | string>>()
  for (const p of equityCurve) {
    byDate.set(p.date, { date: p.date, strategy: p.equity })
  }
  for (const [name, points] of Object.entries(baselineCurves)) {
    for (const p of points) {
      const row = byDate.get(p.date) ?? { date: p.date }
      row[name] = p.equity
      byDate.set(p.date, row)
    }
  }
  const data = Array.from(byDate.values()).sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  )

  const series = ['strategy', ...Object.keys(baselineCurves)]
  const warmup = detectWarmup(equityCurve)

  return (
    <div className="min-w-0">
      <div className="relative isolate h-64 w-full min-w-0 overflow-hidden sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2eae6" vertical={false} />
            {warmup?.endDate ? (
              <ReferenceArea
                x1={data[0]?.date as string}
                x2={warmup.endDate}
                fill="#0f1c1a"
                fillOpacity={0.05}
                stroke="none"
                ifOverflow="extendDomain"
              />
            ) : null}
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#5c6b66' }}
              minTickGap={48}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: string) => v.slice(0, 7)}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#5c6b66' }}
              domain={['auto', 'auto']}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `$${Math.round(v).toLocaleString()}`}
              width={56}
            />
            <Tooltip
              formatter={(value) => [
                typeof value === 'number'
                  ? `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                  : String(value ?? ''),
              ]}
              labelFormatter={(label) => String(label)}
              contentStyle={{
                borderRadius: 6,
                border: '1px solid #d0dbd6',
                fontSize: 12,
                background: '#fff',
              }}
            />
            <Legend
              formatter={(v) => String(v).replace(/_/g, ' ')}
              wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            />
            {series.map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={key}
                stroke={SERIES_COLORS[key] ?? '#44403c'}
                strokeWidth={key === 'strategy' ? 2 : 1.25}
                dot={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {warmup ? (
        <p className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs text-muted">
          <span
            aria-hidden
            className="inline-block size-2.5 shrink-0 translate-y-px rounded-sm bg-ink/10 ring-1 ring-ink/15"
          />
          <span>
            Shaded: <span className="text-ink">warm-up</span> to {warmup.endDate} — no positions
            held while long-horizon signals build history.
          </span>
          <span className="font-mono text-[11px]">
            {fmtPct(warmup.share, 0)} of the sample, still included in the metrics above.
          </span>
        </p>
      ) : null}
    </div>
  )
}
