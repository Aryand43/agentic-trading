import { Hint, HintLabel } from './Hint'
import { HINTS } from '../content/hints'
import { fmtNum, fmtPct, TONE_TEXT, toneOf } from '../lib/format'
import {
  buildSegmentGroups,
  THIN_SEGMENT_DAYS,
  type SegmentGroup,
  type SegmentRow,
  type SegmentsPayload,
} from '../lib/segments'

type Props = { segments: SegmentsPayload }

const BASIS_NOTE: Record<SegmentGroup['basis'], string> = {
  time: 'Time split',
  holdings: 'Holdings split',
}

function DaysCell({ row, group }: { row: SegmentRow; group: SegmentGroup }) {
  if (!group.hasCounts) {
    return (
      <td className="py-2.5 pr-4 text-right">
        <Hint text={HINTS.segmentNoCount} side="top">
          <span className="cursor-help font-mono text-[12px] text-muted/60">n/a</span>
        </Hint>
      </td>
    )
  }
  if (row.days == null) {
    return <td className="py-2.5 pr-4 text-right font-mono text-[12px] text-muted/60">—</td>
  }
  return (
    <td className="py-2.5 pr-4 text-right">
      <span className="font-mono text-[12px] tabular-nums text-ink">{row.days}d</span>
      {row.share != null ? (
        <span className="ml-1.5 font-mono text-[11px] tabular-nums text-muted">
          {fmtPct(row.share, 0)}
        </span>
      ) : null}
    </td>
  )
}

function SegmentRowView({ row, group }: { row: SegmentRow; group: SegmentGroup }) {
  const metricCols = 3

  return (
    <tr className="border-b border-line/70 last:border-0">
      <th scope="row" className="py-2.5 pr-4 text-left align-middle font-sans font-medium text-ink">
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {row.label}
          {row.status === 'thin' ? (
            <Hint text={HINTS.segmentThin(THIN_SEGMENT_DAYS)} side="top">
              <span className="cursor-help rounded border border-rose/30 bg-rose-soft/40 px-1.5 py-px font-mono text-[10px] font-medium uppercase tracking-wide text-rose">
                low sample
              </span>
            </Hint>
          ) : null}
        </span>
      </th>

      <DaysCell row={row} group={group} />

      {row.status === 'empty' ? (
        <td
          colSpan={metricCols}
          className="py-2.5 text-right text-[12px] italic text-muted/80"
        >
          <Hint text={HINTS.segmentEmpty} side="top">
            <span className="cursor-help border-b border-dotted border-muted/40 not-italic font-mono text-[11px] uppercase tracking-wide">
              no activity
            </span>
          </Hint>
        </td>
      ) : (
        <>
          <td
            className={`py-2.5 pr-4 text-right font-mono text-[13px] tabular-nums ${TONE_TEXT[toneOf(row.metrics.sharpe)]}`}
          >
            {fmtNum(row.metrics.sharpe)}
          </td>
          <td
            className={`py-2.5 pr-4 text-right font-mono text-[13px] tabular-nums ${TONE_TEXT[toneOf(row.metrics.total_return)]}`}
          >
            {fmtPct(row.metrics.total_return)}
          </td>
          <td className="py-2.5 text-right font-mono text-[13px] tabular-nums text-ink">
            {fmtPct(row.metrics.hit_rate)}
          </td>
        </>
      )}
    </tr>
  )
}

function GroupTable({ group }: { group: SegmentGroup }) {
  return (
    <section className="min-w-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="text-sm font-semibold tracking-tight text-ink">{group.title}</h3>
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted/70">
          {BASIS_NOTE[group.basis]}
        </span>
      </div>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-105 text-left text-sm">
          <thead>
            <tr className="border-b border-line text-[10px] uppercase tracking-wide text-muted">
              <th scope="col" className="pb-2 pr-4 font-medium">
                Segment
              </th>
              <th scope="col" className="pb-2 pr-4 text-right font-medium">
                <HintLabel label="Days" text={HINTS.segmentDays} />
              </th>
              <th scope="col" className="pb-2 pr-4 text-right font-medium">
                <HintLabel label="Sharpe" text={HINTS.sharpe} />
              </th>
              <th scope="col" className="pb-2 pr-4 text-right font-medium">
                <HintLabel label="Return" text={HINTS.segmentReturn} />
              </th>
              <th scope="col" className="pb-2 text-right font-medium">
                <HintLabel label="Hit rate" text={HINTS.hitRate} />
              </th>
            </tr>
          </thead>
          <tbody>
            {group.rows.map((row) => (
              <SegmentRowView key={row.key} row={row} group={group} />
            ))}
          </tbody>
        </table>
      </div>

      {group.unclassifiedDays ? (
        <p className="mt-1.5 font-mono text-[11px] text-muted">
          {group.unclassifiedDays} day{group.unclassifiedDays === 1 ? '' : 's'} unclassified, not
          shown above.
        </p>
      ) : null}
    </section>
  )
}

export function SegmentReport({ segments }: Props) {
  const groups = buildSegmentGroups(segments)

  if (!groups.length) {
    return <p className="text-sm text-muted">No segment data for this run.</p>
  }

  return (
    <div className="flex min-w-0 flex-col gap-7">
      {groups.map((group) => (
        <GroupTable key={group.key} group={group} />
      ))}
    </div>
  )
}
