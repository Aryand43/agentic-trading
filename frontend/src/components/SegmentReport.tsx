import type { MetricsBlock } from '../types/pipeline'

function fmtPct(x: number | undefined): string {
  if (x == null || Number.isNaN(x)) return '—'
  return `${(x * 100).toFixed(1)}%`
}

function fmtSharpe(x: number | undefined): string {
  if (x == null || Number.isNaN(x)) return '—'
  return x.toFixed(2)
}

function isMetrics(v: unknown): v is MetricsBlock {
  return Boolean(v) && typeof v === 'object' && 'sharpe' in (v as object)
}

type Props = {
  segments: {
    regime?: Record<string, unknown>
    volatility?: Record<string, unknown>
    industry?: Record<string, unknown>
  }
}

function pickRows(
  block: Record<string, unknown> | undefined,
  preferred: string[],
): { name: string; m: MetricsBlock }[] {
  if (!block) return []
  const keys = preferred.filter((k) => isMetrics(block[k]))
  const rest = Object.keys(block).filter(
    (k) => !k.startsWith('_') && isMetrics(block[k]) && !keys.includes(k),
  )
  return [...keys, ...rest].map((name) => ({ name, m: block[name] as MetricsBlock }))
}

function SegmentBlock({
  title,
  rows,
}: {
  title: string
  rows: { name: string; m: MetricsBlock }[]
}) {
  if (!rows.length) return null
  return (
    <div>
      <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted">{title}</h3>
      <ul className="space-y-0 divide-y divide-line/70 border-t border-line">
        {rows.map(({ name, m }) => (
          <li key={name} className="flex items-baseline justify-between gap-3 py-2 text-sm">
            <span className="font-medium capitalize text-ink">{name}</span>
            <span className="font-mono text-[12px] tabular-nums text-muted">
              S {fmtSharpe(m.sharpe)}
              <span className="mx-1.5 text-line">·</span>
              {fmtPct(m.total_return)}
              <span className="mx-1.5 text-line">·</span>
              hit {fmtPct(m.hit_rate)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function SegmentReport({ segments }: Props) {
  const regime = pickRows(segments.regime, ['bull', 'bear'])
  const vol = pickRows(segments.volatility, ['low', 'mid', 'high'])
  const industry = pickRows(segments.industry, []).filter((r) => r.name !== '_ticker_sector_map')

  if (!regime.length && !vol.length && !industry.length) {
    return <p className="text-sm text-muted">No segment data for this run.</p>
  }

  return (
    <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
      <SegmentBlock title="Regime" rows={regime} />
      <SegmentBlock title="Volatility" rows={vol} />
      <SegmentBlock title="Industry" rows={industry} />
    </div>
  )
}
