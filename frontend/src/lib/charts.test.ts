import { describe, expect, it } from 'vitest'
import { niceCeil, sparkScale, symmetricDomain } from './charts'

describe('niceCeil', () => {
  it('rounds up to 1/2/5 x 10^n', () => {
    expect(niceCeil(0.11)).toBeCloseTo(0.2, 10)
    expect(niceCeil(0.3)).toBeCloseTo(0.5, 10)
    expect(niceCeil(0.6)).toBeCloseTo(1, 10)
    expect(niceCeil(1.4)).toBeCloseTo(2, 10)
    expect(niceCeil(7)).toBeCloseTo(10, 10)
  })

  it('is zero for non-positive or non-finite input', () => {
    expect(niceCeil(0)).toBe(0)
    expect(niceCeil(-1)).toBe(0)
    expect(niceCeil(Number.NaN)).toBe(0)
  })
})

describe('symmetricDomain', () => {
  it('stays symmetric so signs read at one scale', () => {
    const [lo, hi] = symmetricDomain([0.4, -0.1], 0.25)
    expect(lo).toBe(-hi)
  })

  it('zooms to small values instead of pinning to the theoretical range', () => {
    // Real conviction values. On a fixed [-1,1] axis these are hairlines.
    const [, hi] = symmetricDomain([0.09, -0.04, 0.11], 0.25)
    expect(hi).toBeLessThanOrEqual(0.25)
  })

  it('does not magnify a near-zero book past minSpan', () => {
    const [, hi] = symmetricDomain([0.001, -0.002], 0.25)
    expect(hi).toBe(0.25)
  })

  it('expands past minSpan when the data needs it', () => {
    // Observed live weights, which breach the requested limits.
    const [, hi] = symmetricDomain([0.4685, 0.7658, 0.7658], 0.1)
    expect(hi).toBeGreaterThanOrEqual(0.7658)
  })

  it('handles an empty or non-finite book', () => {
    expect(symmetricDomain([], 0.25)).toEqual([-0.25, 0.25])
    expect(symmetricDomain([Number.NaN], 0.25)).toEqual([-0.25, 0.25])
  })
})

describe('sparkScale', () => {
  it('puts the baseline at the bottom when every value is positive', () => {
    const s = sparkScale([0.2, 0.5, 0.9])
    expect(s.zero).toBeCloseTo(1, 10)
    expect(s.bars.every((b) => !b.negative)).toBe(true)
  })

  it('scales bars against the observed range, not a fixed floor', () => {
    const s = sparkScale([0.25, 0.5, 1])
    expect(s.bars[2].height).toBeCloseTo(1, 10)
    expect(s.bars[0].height).toBeCloseTo(0.25, 10)
  })

  it('distinguishes a negative value from a small positive one', () => {
    // The old sparkline floored both to the same 8px and lost the sign.
    const s = sparkScale([0.05, -0.05])
    expect(s.bars[0].negative).toBe(false)
    expect(s.bars[1].negative).toBe(true)
    expect(s.bars[1].fromTop).toBeGreaterThanOrEqual(s.zero)
  })

  it('places the baseline between positive and negative extents', () => {
    const s = sparkScale([1, -1])
    expect(s.zero).toBeCloseTo(0.5, 10)
  })

  it('gives an exact zero no height at all', () => {
    const s = sparkScale([0, 1])
    expect(s.bars[0].height).toBe(0)
  })

  it('keeps a tiny non-zero value visible', () => {
    const s = sparkScale([0.0001, 1])
    expect(s.bars[0].height).toBeGreaterThan(0)
  })

  it('survives an all-zero series without dividing by zero', () => {
    const s = sparkScale([0, 0, 0])
    expect(s.zero).toBe(0.5)
    expect(s.bars.every((b) => b.height === 0)).toBe(true)
  })

  it('treats missing values as zero rather than NaN', () => {
    const s = sparkScale([null, undefined, 1])
    expect(s.bars.every((b) => Number.isFinite(b.height))).toBe(true)
  })
})
