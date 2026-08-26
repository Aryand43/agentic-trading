import { useMemo, useState } from 'react'
import type { SignalEventRow, TradeAuditRow } from '../types/pipeline'

type Props = {
  trades: TradeAuditRow[]
  signalEvents?: SignalEventRow[]
  truncated?: boolean
}

function fmtPx(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(2)
}

function fmtPnl(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}`
}

function fmtRet(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(2)}%`
}

export function TradeAuditTable({ trades, signalEvents = [], truncated }: Props) {
  const [ticker, setTicker] = useState('')
  const [horizon, setHorizon] = useState('')
  const [reason, setReason] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const tickers = useMemo(
    () => Array.from(new Set(trades.map((t) => t.ticker))).sort(),
    [trades],
  )
  const horizons = useMemo(
    () => Array.from(new Set(trades.map((t) => t.signal_horizon))).sort(),
    [trades],
  )
  const reasons = useMemo(
    () =>
      Array.from(new Set(trades.map((t) => t.exit_reason).filter(Boolean) as string[])).sort(),
    [trades],
  )

  const filtered = trades.filter((t) => {
    if (ticker && t.ticker !== ticker) return false
    if (horizon && t.signal_horizon !== horizon) return false
    if (reason && t.exit_reason !== reason) return false
    return true
  })

  const selected = filtered.find((t) => t.trade_id === selectedId) ?? null
  const linked = selected
    ? signalEvents.find(
        (e) =>
          e.ticker === selected.ticker &&
          e.horizon === selected.signal_horizon &&
          e.date === selected.signal_date,
      )
    : null

  if (!trades.length) {
    return <p className="text-sm text-muted">No trades in this window.</p>
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <select
          aria-label="Filter ticker"
          className="h-9 rounded-md border border-line bg-white px-2 font-mono text-xs"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
        >
          <option value="">All tickers</option>
          {tickers.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter horizon"
          className="h-9 rounded-md border border-line bg-white px-2 font-mono text-xs"
          value={horizon}
          onChange={(e) => setHorizon(e.target.value)}
        >
          <option value="">All horizons</option>
          {horizons.map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter exit reason"
          className="h-9 rounded-md border border-line bg-white px-2 font-mono text-xs"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        >
          <option value="">All exits</option>
          {reasons.map((r) => (
            <option key={r} value={r}>
              {r.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
      </div>
      {truncated ? (
        <p className="font-mono text-[11px] text-muted">Showing first {trades.length} trades.</p>
      ) : null}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm" data-testid="trade-audit-table">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
              <th className="pb-2 pr-3 font-medium">Date</th>
              <th className="pb-2 pr-3 font-medium">Ticker</th>
              <th className="pb-2 pr-3 font-medium">Horizon</th>
              <th className="pb-2 pr-3 font-medium">Signal</th>
              <th className="pb-2 pr-3 font-medium">Entry</th>
              <th className="pb-2 pr-3 font-medium">Exit</th>
              <th className="pb-2 pr-3 font-medium">Reason</th>
              <th className="pb-2 pr-3 font-medium">PnL</th>
              <th className="pb-2 pr-3 font-medium">Return</th>
              <th className="pb-2 font-medium">Dir</th>
            </tr>
          </thead>
          <tbody className="font-mono text-[12px]">
            {filtered.map((t) => (
              <tr
                key={t.trade_id}
                className={`cursor-pointer border-b border-line/70 last:border-0 ${
                  selectedId === t.trade_id ? 'bg-teal-soft/40' : ''
                }`}
                onClick={() => setSelectedId(t.trade_id)}
              >
                <td className="py-2 pr-3">{t.entry_date || t.signal_date}</td>
                <td className="py-2 pr-3">{t.ticker}</td>
                <td className="py-2 pr-3">{t.signal_horizon}</td>
                <td className="py-2 pr-3">
                  {t.signal_side} {t.signal_value.toFixed(2)}
                </td>
                <td className="py-2 pr-3">{fmtPx(t.entry_price)}</td>
                <td className="py-2 pr-3">{fmtPx(t.exit_price)}</td>
                <td className="py-2 pr-3">{t.exit_reason?.replace(/_/g, ' ') ?? '—'}</td>
                <td className="py-2 pr-3">{fmtPnl(t.net_pnl)}</td>
                <td className="py-2 pr-3">{fmtRet(t.return)}</td>
                <td className="py-2">{t.position_direction}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected ? (
        <div
          className="rounded-lg border border-line bg-white/80 px-4 py-3 text-sm"
          data-testid="trade-detail"
        >
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Signal → weight → entry → exit → PnL
          </p>
          <p className="mt-2 font-mono text-[12px] text-ink">
            {selected.signal_date} {selected.ticker} {selected.signal_horizon}:{' '}
            {selected.signal_side} {selected.signal_value.toFixed(3)}
            {linked?.weight != null ? ` → weight ${linked.weight.toFixed(3)}` : ''}
            {` → entry ${fmtPx(selected.entry_price)} (${selected.entry_date ?? '—'})`}
            {` → exit ${fmtPx(selected.exit_price)} (${selected.exit_date ?? '—'}, ${
              selected.exit_reason?.replace(/_/g, ' ') ?? '—'
            })`}
            {` → PnL ${fmtPnl(selected.net_pnl)}`}
          </p>
        </div>
      ) : (
        <p className="text-xs text-muted">Select a row to trace signal → trade → PnL.</p>
      )}
    </div>
  )
}
