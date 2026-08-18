/** Reading structure out of an equity curve.
 *
 * The backtest engine holds zero exposure for a warmup period (long-horizon
 * signals need ~1y of history first), but those flat bars are still returned in
 * the curve and still counted in the headline metrics. Detecting the flat prefix
 * lets the chart say so instead of drawing a year of apparently live-but-static
 * trading.
 */
import type { EquityPoint } from '../types/pipeline'

/** Relative move below which two equity values count as unchanged. */
const FLAT_EPSILON = 1e-9

export type WarmupInfo = {
  /** Index of the first point where equity actually moves. */
  firstActiveIndex: number
  /** Date of the last flat point, i.e. where the shaded band ends. */
  endDate: string | null
  /** Number of leading flat points. */
  points: number
  /** Share of the curve that is flat. */
  share: number
}

/** Leading run of points whose equity never changes. */
export function detectWarmup(curve: EquityPoint[]): WarmupInfo | null {
  if (curve.length < 2) return null

  const first = curve[0].equity
  let i = 1
  while (i < curve.length) {
    const rel = Math.abs(curve[i].equity - first) / (Math.abs(first) || 1)
    if (rel > FLAT_EPSILON) break
    i += 1
  }

  // No flat prefix, or the whole series is flat (nothing useful to say).
  if (i < 2 || i >= curve.length) return null

  return {
    firstActiveIndex: i,
    endDate: curve[i - 1].date,
    points: i,
    share: i / curve.length,
  }
}
