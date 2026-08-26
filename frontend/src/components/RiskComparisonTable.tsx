import type { RiskComparisonRow } from '../types/pipeline'

type Props = {
  rows: RiskComparisonRow[]
}

function fmtNum(value: number | null | undefined, digits = 4): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(digits)
}

function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function methodLabel(method: string): string {
  if (method === 'ewma_cornish_fisher') return 'EWMA / Cornish-Fisher'
  if (method === 'historical_std') return 'Historical std'
  if (method === 'historical_var') return 'Historical VaR'
  return method.replace(/_/g, ' ')
}

export function RiskComparisonTable({ rows }: Props) {
  if (!rows.length) {
    return <p className="text-sm text-muted">No risk comparison for this window.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm" data-testid="risk-comparison-table">
        <thead>
          <tr className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
            <th className="pb-2 pr-3 font-medium">Method</th>
            <th className="pb-2 pr-3 font-medium">Horizon</th>
            <th className="pb-2 pr-3 font-medium">Predicted</th>
            <th className="pb-2 pr-3 font-medium">Realized</th>
            <th className="pb-2 pr-3 font-medium">Error</th>
            <th className="pb-2 pr-3 font-medium">Breach</th>
            <th className="pb-2 font-medium">n</th>
          </tr>
        </thead>
        <tbody className="font-mono text-[12px]">
          {rows.map((row, i) => (
            <tr key={`${row.method}-${row.horizon}-${row.confidence ?? 'na'}-${i}`} className="border-b border-line/70 last:border-0">
              <td className="py-2 pr-3 font-sans">
                {methodLabel(row.method)}
                {row.confidence != null ? ` ${(row.confidence * 100).toFixed(0)}%` : ''}
              </td>
              <td className="py-2 pr-3">{row.horizon}</td>
              <td className="py-2 pr-3">{fmtNum(row.predicted_risk)}</td>
              <td className="py-2 pr-3">{fmtNum(row.realized_risk)}</td>
              <td className="py-2 pr-3">{fmtNum(row.error)}</td>
              <td className="py-2 pr-3">{fmtPct(row.breach_rate)}</td>
              <td className={`py-2 ${row.low_sample || row.n_obs < 120 ? 'text-rose' : ''}`}>
                {row.n_obs || '—'}
                {row.low_sample || row.n_obs < 120 ? ' low' : ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
