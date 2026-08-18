import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { symmetricDomain } from '../lib/charts'

type Props = {
  values: Record<string, number>
  /** Tooltip row label, e.g. "Conviction". */
  label: string
  /** Smallest half-span the axis will zoom to. */
  minSpan: number
  /** Decimals in the axis ticks. */
  tickDigits?: number
  yAxisWidth?: number
}

/** Bar chart for a signed per-ticker quantity.
 *
 * Conviction and weights were separate components differing only in axis
 * domain and tooltip text. Both now share this, which also adds the zero
 * reference line they were missing — without it a small negative bar was
 * indistinguishable from a small positive one.
 */
export function SignedBarChart({
  values,
  label,
  minSpan,
  tickDigits = 2,
  yAxisWidth = 44,
}: Props) {
  const data = Object.entries(values).map(([ticker, value]) => ({ ticker, value }))
  const domain = symmetricDomain(
    data.map((d) => d.value),
    minSpan,
  )

  return (
    <div className="h-64 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#c5d2ce" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="ticker"
            tick={{ fill: '#5b6f6a', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={domain}
            tick={{ fill: '#5b6f6a', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={yAxisWidth}
            tickFormatter={(v: number) => v.toFixed(tickDigits)}
          />
          <Tooltip
            cursor={{ fill: 'rgba(15,28,26,0.04)' }}
            formatter={(value) => [Number(value).toFixed(3), label]}
            contentStyle={{
              borderRadius: 8,
              border: '1px solid #c5d2ce',
              fontFamily: 'IBM Plex Mono, monospace',
              fontSize: 12,
            }}
          />
          <ReferenceLine y={0} stroke="#5c6b66" strokeWidth={1} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell key={entry.ticker} fill={entry.value >= 0 ? '#0f766e' : '#be123c'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
