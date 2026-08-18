/** Axis maths for the signed bar charts, kept pure so the scaling is testable.
 *
 * The desk's signed quantities (conviction, weights, utility) are small far more
 * often than they are large. A fixed [-1, 1] axis renders a real conviction of
 * 0.1 as a hairline indistinguishable from zero — which is how the live book
 * came to look flat. These helpers zoom to the data while keeping zero centred
 * and the sign readable.
 */

/** Round up to 1/2/5 x 10^n so ticks land on readable values. */
export function niceCeil(x: number): number {
  if (!Number.isFinite(x) || x <= 0) return 0
  const exp = Math.floor(Math.log10(x))
  const pow = 10 ** exp
  const frac = x / pow
  const nice = frac <= 1 ? 1 : frac <= 2 ? 2 : frac <= 5 ? 5 : 10
  return nice * pow
}

/** Symmetric domain around zero, so positive and negative read at one scale.
 *
 * `minSpan` stops a book of near-zero values from being magnified into
 * apparently huge bars.
 */
export function symmetricDomain(values: number[], minSpan: number): [number, number] {
  const finite = values.filter((v) => Number.isFinite(v))
  const maxAbs = finite.length ? Math.max(...finite.map(Math.abs)) : 0
  const span = Math.max(minSpan, niceCeil(maxAbs * 1.15))
  return [-span, span]
}

/** Baseline offset and bar heights for a sparkline drawn from zero.
 *
 * Returns fractions of the track height: `zero` is where the baseline sits from
 * the top, and each bar's `height`/`fromTop` place it against that baseline.
 */
export type SparkBar = {
  /** Fraction of track height, 0..1. */
  height: number
  /** Fraction from the top of the track where the bar starts. */
  fromTop: number
  negative: boolean
}

export type SparkScale = {
  /** Fraction from the top where zero sits. */
  zero: number
  bars: SparkBar[]
}

/** Minimum visible fraction so a tiny non-zero value is not invisible. */
const MIN_VISIBLE = 0.02

export function sparkScale(values: (number | null | undefined)[]): SparkScale {
  const nums = values.map((v) => (Number.isFinite(v as number) ? (v as number) : 0))
  const max = Math.max(0, ...nums)
  const min = Math.min(0, ...nums)
  const range = max - min

  // Flat-at-zero series: baseline in the middle, no bars.
  if (range === 0) {
    return { zero: 0.5, bars: nums.map(() => ({ height: 0, fromTop: 0.5, negative: false })) }
  }

  const zero = max / range

  return {
    zero,
    bars: nums.map((v) => {
      const frac = Math.abs(v) / range
      const height = v === 0 ? 0 : Math.max(MIN_VISIBLE, frac)
      return {
        height,
        fromTop: v >= 0 ? zero - height : zero,
        negative: v < 0,
      }
    }),
  }
}
