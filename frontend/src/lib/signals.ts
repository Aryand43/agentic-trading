/** Telling "no signal" apart from "neutral signal" in the horizon grid.
 *
 * Several horizon strategies return a hard 0.0 when they lack enough history
 * (`signal_15d` and `signal_1m` need 252 bars; the live panel supplies 251), and
 * the API sends that indistinguishably from a genuine neutral reading. The grid
 * therefore showed permanently dead horizons as confident `+0.00` votes.
 *
 * The API cannot currently say which it is, but an entire column reading exactly
 * zero across every ticker is a guard tripping, not a coincidence — real signals
 * are continuous and essentially never land on exact zero for every name at once.
 */

/** Ticker count below which an all-zero column is not yet evidence of anything. */
export const MIN_TICKERS_FOR_INFERENCE = 2

export function isExactlyZero(x: number | null | undefined): boolean {
  return x === 0 || Object.is(x, -0)
}

/**
 * Horizons whose signal is exactly zero for every ticker.
 *
 * Returns an empty set when there are too few tickers to distinguish a dead
 * horizon from a genuinely flat one.
 */
export function inactiveHorizons(
  signals: Record<string, Record<string, number>>,
  horizons: string[],
): Set<string> {
  const tickers = Object.keys(signals)
  if (tickers.length < MIN_TICKERS_FOR_INFERENCE) return new Set()

  const dead = new Set<string>()
  for (const horizon of horizons) {
    const values = tickers.map((t) => signals[t]?.[horizon])
    // Only judge a horizon every ticker actually reported.
    if (values.some((v) => v == null)) continue
    if (values.every((v) => isExactlyZero(v))) dead.add(horizon)
  }
  return dead
}
