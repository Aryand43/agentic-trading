import { describe, expect, it } from 'vitest'
import { checkLimits, grossExposureOf, largestPositionOf } from './limits'

describe('grossExposureOf', () => {
  it('sums absolute weights so shorts add to gross', () => {
    expect(grossExposureOf({ A: 0.5, B: -0.5 })).toBeCloseTo(1.0, 10)
  })

  it('is zero for an empty book', () => {
    expect(grossExposureOf({})).toBe(0)
  })
})

describe('largestPositionOf', () => {
  it('picks the largest by absolute size, keeping the sign', () => {
    expect(largestPositionOf({ A: 0.2, B: -0.7, C: 0.5 })).toEqual({ ticker: 'B', weight: -0.7 })
  })

  it('returns null for an empty book', () => {
    expect(largestPositionOf({})).toBeNull()
  })
})

describe('checkLimits', () => {
  const requested = { maxPosition: 0.15, grossExposure: 1.0 }

  it('reports nothing when the book respects both limits', () => {
    expect(checkLimits({ A: 0.1, B: -0.05 }, requested)).toEqual([])
  })

  it('catches the real observed breach from the live pipeline', () => {
    // Weights actually returned for max_position=0.15, gross_exposure=1.0.
    const weights = { AAPL: 0.4685, MSFT: 0.7658, NVDA: 0.7658 }
    const breaches = checkLimits(weights, requested)

    expect(breaches.map((b) => b.kind)).toEqual(['max_position', 'gross_exposure'])

    const pos = breaches[0]
    expect(pos.ticker).toBe('MSFT')
    expect(pos.actual).toBeCloseTo(0.7658, 4)
    expect(pos.ratio).toBeCloseTo(5.105, 2)

    const gross = breaches[1]
    expect(gross.actual).toBeCloseTo(2.0001, 3)
    expect(gross.ratio).toBeCloseTo(2.0, 2)
  })

  it('reports only the breached limit', () => {
    // Within per-name cap (0.15 each), but 8 x 0.15 = 1.2 gross.
    const breaches = checkLimits(
      { A: 0.15, B: 0.15, C: 0.15, D: 0.15, E: 0.15, F: 0.15, G: 0.15, H: 0.15 },
      requested,
    )
    expect(breaches.map((b) => b.kind)).toEqual(['gross_exposure'])
  })

  it('ignores float noise at the boundary', () => {
    expect(checkLimits({ A: 0.15 + 1e-9 }, requested)).toEqual([])
    const atGross = { A: 0.125, B: 0.125, C: 0.125, D: 0.125, E: 0.125, F: 0.125, G: 0.125, H: 0.125 + 1e-9 }
    expect(checkLimits(atGross, requested)).toEqual([])
  })

  it('treats shorts as breaches too', () => {
    const breaches = checkLimits({ A: -0.9 }, requested)
    expect(breaches[0].kind).toBe('max_position')
    expect(breaches[0].ticker).toBe('A')
  })

  it('returns nothing for an empty book', () => {
    expect(checkLimits({}, requested)).toEqual([])
  })
})
