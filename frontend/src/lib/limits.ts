/** Client-side verification that the book we got back respects the limits we asked for.
 *
 * The desk sends `max_position` and `gross_exposure` with every run and gets the
 * resulting weights back, so it can check the answer rather than trusting it.
 * At time of writing the backend applies its volatility target *after* capping
 * and normalising, which can push both limits well past what was requested.
 */

/** Tolerance for float noise before a breach is worth reporting. */
export const LIMIT_EPSILON = 1e-4

export type LimitBreach = {
  kind: 'max_position' | 'gross_exposure'
  requested: number
  actual: number
  /** Ticker responsible, for per-name breaches. */
  ticker?: string
  /** How many times over the requested limit, e.g. 5.1. */
  ratio: number
}

export function grossExposureOf(weights: Record<string, number>): number {
  return Object.values(weights).reduce((sum, w) => sum + Math.abs(w), 0)
}

export function largestPositionOf(
  weights: Record<string, number>,
): { ticker: string; weight: number } | null {
  let best: { ticker: string; weight: number } | null = null
  for (const [ticker, w] of Object.entries(weights)) {
    const abs = Math.abs(w)
    if (!best || abs > Math.abs(best.weight)) best = { ticker, weight: w }
  }
  return best
}

export function checkLimits(
  weights: Record<string, number>,
  requested: { maxPosition: number; grossExposure: number },
): LimitBreach[] {
  const breaches: LimitBreach[] = []
  if (!weights || Object.keys(weights).length === 0) return breaches

  const largest = largestPositionOf(weights)
  if (largest && Math.abs(largest.weight) > requested.maxPosition + LIMIT_EPSILON) {
    breaches.push({
      kind: 'max_position',
      requested: requested.maxPosition,
      actual: Math.abs(largest.weight),
      ticker: largest.ticker,
      ratio: Math.abs(largest.weight) / requested.maxPosition,
    })
  }

  const gross = grossExposureOf(weights)
  if (gross > requested.grossExposure + LIMIT_EPSILON) {
    breaches.push({
      kind: 'gross_exposure',
      requested: requested.grossExposure,
      actual: gross,
      ratio: gross / requested.grossExposure,
    })
  }

  return breaches
}
