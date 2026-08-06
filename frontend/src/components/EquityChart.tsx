import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { EquityPoint } from '../types/pipeline'

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
  initialCapital: number
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

  return (
    <div className="relative isolate h-64 w-full min-w-0 overflow-hidden sm:h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2eae6" vertical={false} />
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
  )
}
