import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { EquityPoint, TradeAuditRow } from '../types/pipeline'

const SERIES_COLORS: Record<string, string> = {
  strategy: '#0f766e',
  buy_and_hold: '#78716c',
  sma_cross: '#c2410c',
  rsi_mean_reversion: '#57534e',
  momentum_20d: '#0e7490',
}

const MARKER_COLORS: Record<string, string> = {
  buy: '#0f766e',
  sell: '#be123c',
  take_profit: '#0e7490',
  stop_loss: '#9f1239',
  horizon_end: '#a16207',
  exit: '#57534e',
}

type Props = {
  equityCurve: EquityPoint[]
  baselineCurves?: Record<string, EquityPoint[]>
  initialCapital: number
  trades?: TradeAuditRow[]
}

function fmtMoney(value: number): string {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function fmtPnl(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}`
}

export function EquityChart({
  equityCurve,
  baselineCurves = {},
  trades = [],
}: Props) {
  const byDate = new Map<string, Record<string, number | string | null>>()
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

  const tradesByDate = new Map<string, TradeAuditRow[]>()
  const addTrade = (date: string | null | undefined, trade: TradeAuditRow) => {
    if (!date) return
    const list = tradesByDate.get(date) ?? []
    list.push(trade)
    tradesByDate.set(date, list)
  }
  for (const trade of trades) {
    addTrade(trade.entry_date, trade)
    addTrade(trade.exit_date, trade)
  }

  for (const [date, list] of tradesByDate.entries()) {
    const row = byDate.get(date)
    if (!row || typeof row.strategy !== 'number') continue
    const y = row.strategy
    if (list.some((t) => t.entry_date === date && t.signal_side === 'buy')) {
      row.buyMark = y
    }
    if (list.some((t) => t.entry_date === date && t.signal_side === 'sell')) {
      row.sellMark = y
    }
    if (list.some((t) => t.exit_date === date && t.exit_reason === 'take_profit')) {
      row.tpMark = y
    }
    if (list.some((t) => t.exit_date === date && t.exit_reason === 'stop_loss')) {
      row.slMark = y
    }
    if (
      list.some(
        (t) =>
          t.exit_date === date &&
          t.exit_reason !== 'take_profit' &&
          t.exit_reason !== 'stop_loss' &&
          t.exit_reason != null,
      )
    ) {
      row.exitMark = y
    }
  }

  const data = Array.from(byDate.values()).sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  )
  const series = ['strategy', ...Object.keys(baselineCurves)]

  const hasBuy = data.some((row) => typeof row.buyMark === 'number')
  const hasSell = data.some((row) => typeof row.sellMark === 'number')

  return (
    <div className="relative isolate h-64 w-full min-w-0 overflow-hidden sm:h-72">
      <div
        data-testid="trade-markers"
        data-buy={hasBuy ? 'true' : 'false'}
        data-sell={hasSell ? 'true' : 'false'}
        className="hidden"
      />
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
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
            tickFormatter={(v: number) => fmtMoney(v)}
            width={56}
          />
          <Tooltip
            content={({ label, payload }) => {
              const date = String(label ?? '')
              const nearby = tradesByDate.get(date) ?? []
              return (
                <div
                  className="max-w-xs rounded-md border border-line bg-white px-3 py-2 text-xs shadow-sm"
                  data-testid="equity-tooltip"
                >
                  <p className="font-medium text-ink">{date}</p>
                  {(payload ?? [])
                    .filter((p) => p.dataKey && series.includes(String(p.dataKey)))
                    .map((p) => (
                      <p key={String(p.dataKey)} className="text-muted">
                        {String(p.name).replace(/_/g, ' ')}:{' '}
                        {typeof p.value === 'number' ? fmtMoney(p.value) : '—'}
                      </p>
                    ))}
                  {nearby.slice(0, 4).map((t) => (
                    <p key={t.trade_id} className="mt-1 text-ink">
                      {t.ticker} {t.signal_horizon} {t.signal_side}
                      {t.exit_reason ? ` · ${t.exit_reason.replace(/_/g, ' ')}` : ''}
                      {t.entry_price != null ? ` · in ${t.entry_price.toFixed(2)}` : ''}
                      {t.exit_price != null ? ` · out ${t.exit_price.toFixed(2)}` : ''}
                      {` · PnL ${fmtPnl(t.net_pnl)}`}
                    </p>
                  ))}
                </div>
              )
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
              connectNulls={false}
            />
          ))}
          <Scatter dataKey="buyMark" name="buy" fill={MARKER_COLORS.buy} legendType="circle" />
          <Scatter dataKey="sellMark" name="sell" fill={MARKER_COLORS.sell} legendType="circle" />
          <Scatter
            dataKey="tpMark"
            name="take profit"
            fill={MARKER_COLORS.take_profit}
            shape="diamond"
            legendType="diamond"
          />
          <Scatter
            dataKey="slMark"
            name="stop loss"
            fill={MARKER_COLORS.stop_loss}
            shape="triangle"
            legendType="triangle"
          />
          <Scatter
            dataKey="exitMark"
            name="forced exit"
            fill={MARKER_COLORS.horizon_end}
            shape="square"
            legendType="square"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
