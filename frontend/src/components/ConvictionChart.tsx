import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

type ConvictionChartProps = {
  conviction: Record<string, number>
}

export function ConvictionChart({ conviction }: ConvictionChartProps) {
  const data = Object.entries(conviction).map(([ticker, value]) => ({
    ticker,
    value,
  }))

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#c5d2ce" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="ticker" tick={{ fill: '#5b6f6a', fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis
            domain={[-1, 1]}
            tick={{ fill: '#5b6f6a', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <Tooltip
            formatter={(value) => [Number(value).toFixed(3), 'Conviction']}
            contentStyle={{
              borderRadius: 8,
              border: '1px solid #c5d2ce',
              fontFamily: 'IBM Plex Mono, monospace',
              fontSize: 12,
            }}
          />
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
