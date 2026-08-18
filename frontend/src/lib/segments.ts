/** Domain rules for reading the backtest `segments` payload.
 *
 * Two things about that payload drive everything here:
 *
 *  1. Each segment is built by *masking* non-member days to 0.0 and rebuilding a
 *     mini equity curve over the FULL sample. So `n_days` is the length of the
 *     whole backtest, not the size of the segment — it must never be shown as a
 *     sample size.
 *  2. When a segment has no non-zero returns the backend returns a 1-element
 *     sentinel curve, so `n_days === 1` reliably means "nothing happened here",
 *     not "one day of data".
 *
 * Real per-segment day counts exist only for `regime`, under `label_counts`.
 */
import type { MetricsBlock } from '../types/pipeline'

/** `n_days` value the backend emits for a segment with no activity. */
export const EMPTY_SEGMENT_SENTINEL = 1

/** Below this many days a segment is reported but flagged as low-confidence. */
export const THIN_SEGMENT_DAYS = 120

export type SegmentStatus = 'ok' | 'thin' | 'empty'

export type SegmentRow = {
  key: string
  label: string
  metrics: MetricsBlock
  /** True observed days, or null when the payload does not carry a count. */
  days: number | null
  /** Share of the labelled sample, or null when unknown. */
  share: number | null
  status: SegmentStatus
}

export type SegmentGroup = {
  key: 'regime' | 'volatility' | 'industry'
  title: string
  /** What the split actually divides — these are not the same kind of question. */
  basis: 'time' | 'holdings'
  rows: SegmentRow[]
  /** Days that fell outside every reported row (e.g. regime "unknown"). */
  unclassifiedDays: number | null
  /** True when the group carries real per-row day counts. */
  hasCounts: boolean
}

export function isMetrics(v: unknown): v is MetricsBlock {
  return Boolean(v) && typeof v === 'object' && 'sharpe' in (v as object)
}

export function isEmptySegment(m: MetricsBlock): boolean {
  return Number(m.n_days) === EMPTY_SEGMENT_SENTINEL
}

function statusFor(m: MetricsBlock, days: number | null): SegmentStatus {
  if (isEmptySegment(m)) return 'empty'
  if (days != null && days < THIN_SEGMENT_DAYS) return 'thin'
  return 'ok'
}

function readCounts(block: Record<string, unknown> | undefined): Record<string, number> {
  const raw = block?.label_counts
  if (!raw || typeof raw !== 'object') return {}
  const out: Record<string, number> = {}
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof v === 'number' && Number.isFinite(v)) out[k] = v
  }
  return out
}

function buildRows(
  block: Record<string, unknown> | undefined,
  preferred: string[],
  counts: Record<string, number>,
  labelOf: (key: string) => string,
): SegmentRow[] {
  if (!block) return []
  const ordered = preferred.filter((k) => isMetrics(block[k]))
  const rest = Object.keys(block)
    .filter((k) => !k.startsWith('_') && isMetrics(block[k]) && !ordered.includes(k))
    .sort()
  const keys = [...ordered, ...rest]

  // Denominator is every labelled day we know about, including buckets that get
  // no row of their own (regime "unknown"), so shares do not overstate coverage.
  const totalCounted = Object.values(counts).reduce((a, b) => a + b, 0)

  return keys.map((key) => {
    const metrics = block[key] as MetricsBlock
    const days = Object.hasOwn(counts, key) ? counts[key] : null
    const share = days != null && totalCounted > 0 ? days / totalCounted : null
    return { key, label: labelOf(key), metrics, days, share, status: statusFor(metrics, days) }
  })
}

const VOL_LABELS: Record<string, string> = {
  low: 'Calm',
  mid: 'Normal',
  high: 'Turbulent',
}

const REGIME_LABELS: Record<string, string> = {
  bull: 'Bull',
  bear: 'Bear',
}

export type SegmentsPayload = {
  regime?: Record<string, unknown>
  volatility?: Record<string, unknown>
  industry?: Record<string, unknown>
}

export function buildSegmentGroups(segments: SegmentsPayload): SegmentGroup[] {
  const regimeCounts = readCounts(segments.regime)
  const regimeRows = buildRows(
    segments.regime,
    ['bull', 'bear'],
    regimeCounts,
    (k) => REGIME_LABELS[k] ?? k,
  )
  const reportedRegime = regimeRows.reduce((a, r) => a + (r.days ?? 0), 0)
  const totalRegime = Object.values(regimeCounts).reduce((a, b) => a + b, 0)

  const groups: SegmentGroup[] = [
    {
      key: 'regime',
      title: 'Market regime',
      basis: 'time',
      rows: regimeRows,
      unclassifiedDays: totalRegime > 0 ? totalRegime - reportedRegime : null,
      hasCounts: Object.keys(regimeCounts).length > 0,
    },
    {
      key: 'volatility',
      title: 'Market volatility',
      basis: 'time',
      rows: buildRows(segments.volatility, ['low', 'mid', 'high'], {}, (k) => VOL_LABELS[k] ?? k),
      unclassifiedDays: null,
      hasCounts: false,
    },
    {
      key: 'industry',
      title: 'Sector',
      basis: 'holdings',
      rows: buildRows(segments.industry, [], {}, (k) => k),
      unclassifiedDays: null,
      hasCounts: false,
    },
  ]

  return groups.filter((g) => g.rows.length > 0)
}
