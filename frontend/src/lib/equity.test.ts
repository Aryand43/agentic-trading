import { describe, expect, it } from 'vitest'
import { detectWarmup } from './equity'
import type { EquityPoint } from '../types/pipeline'

function curve(values: number[]): EquityPoint[] {
  return values.map((equity, i) => ({
    date: `2024-01-${String((i % 28) + 1).padStart(2, '0')}`,
    equity,
    series: 'strategy',
  }))
}

describe('detectWarmup', () => {
  it('finds a flat prefix and reports where it ends', () => {
    const c = curve([100, 100, 100, 101, 102])
    const w = detectWarmup(c)!
    expect(w.firstActiveIndex).toBe(3)
    expect(w.endDate).toBe(c[2].date)
    expect(w.points).toBe(3)
    expect(w.share).toBeCloseTo(0.6, 10)
  })

  it('returns null when the curve moves immediately', () => {
    expect(detectWarmup(curve([100, 101, 102]))).toBeNull()
  })

  it('returns null when the whole curve is flat', () => {
    // Nothing useful to shade if there is no active period to contrast with.
    expect(detectWarmup(curve([100, 100, 100]))).toBeNull()
  })

  it('returns null for a curve too short to judge', () => {
    expect(detectWarmup([])).toBeNull()
    expect(detectWarmup(curve([100]))).toBeNull()
  })

  it('ignores floating-point dust in the flat region', () => {
    const w = detectWarmup(curve([100, 100 + 1e-12, 100, 105]))!
    expect(w.points).toBe(3)
  })

  it('matches the shape of a real 750-bar run with 260 warmup bars', () => {
    const flat = Array<number>(260).fill(10000)
    const active = Array.from({ length: 490 }, (_, i) => 10000 + i + 1)
    const w = detectWarmup(curve([...flat, ...active]))!
    expect(w.points).toBe(260)
    expect(w.share).toBeCloseTo(260 / 750, 4)
  })
})
