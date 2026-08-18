import { describe, expect, it } from 'vitest'
import { inactiveHorizons, isExactlyZero } from './signals'

const HORIZONS = ['1d', '3d', '5d', '10d', '15d', '1m', '3m']

/** Real live-mode output: 15d and 1m are dead because the 1y panel supplies
 *  251 bars and both strategies guard at 252. */
const LIVE = {
  AAPL: { '1d': -0.707, '3d': 0.223, '5d': -0.0, '10d': -0.159, '15d': 0, '1m': 0, '3m': 0.924 },
  MSFT: { '1d': 0.238, '3d': 0.657, '5d': 0.0, '10d': 0.698, '15d': 0, '1m': 0, '3m': -0.004 },
  NVDA: { '1d': 0.834, '3d': 0.077, '5d': 0.0, '10d': 0.702, '15d': 0, '1m': 0, '3m': -0.151 },
}

describe('isExactlyZero', () => {
  it('matches both signed zeros', () => {
    expect(isExactlyZero(0)).toBe(true)
    expect(isExactlyZero(-0)).toBe(true)
  })

  it('does not match a small non-zero value', () => {
    expect(isExactlyZero(1e-12)).toBe(false)
    expect(isExactlyZero(null)).toBe(false)
    expect(isExactlyZero(undefined)).toBe(false)
  })
})

describe('inactiveHorizons', () => {
  it('finds the horizons that produced nothing for anyone', () => {
    const dead = inactiveHorizons(LIVE, HORIZONS)
    expect([...dead].sort()).toEqual(['15d', '1m', '5d'])
  })

  it('leaves horizons with any non-zero reading alone', () => {
    const dead = inactiveHorizons(LIVE, HORIZONS)
    expect(dead.has('1d')).toBe(false)
    expect(dead.has('3m')).toBe(false)
  })

  it('does not treat one ticker as evidence', () => {
    // A single name legitimately sitting at zero says nothing about the strategy.
    expect(inactiveHorizons({ AAPL: LIVE.AAPL }, HORIZONS).size).toBe(0)
  })

  it('skips a horizon that some ticker did not report', () => {
    const partial = {
      AAPL: { '1d': 0 },
      MSFT: {},
    }
    expect(inactiveHorizons(partial, ['1d']).size).toBe(0)
  })

  it('returns an empty set for an empty book', () => {
    expect(inactiveHorizons({}, HORIZONS).size).toBe(0)
  })

  it('flags a horizon where every ticker is a signed zero', () => {
    const signed = { A: { '1d': -0 }, B: { '1d': 0 } }
    expect(inactiveHorizons(signed, ['1d']).has('1d')).toBe(true)
  })
})
