import { describe, expect, it } from 'vitest'
import { isYearPreset, parseLocalYMD, todayYMD, toLocalYMD, yearsAgoYMD } from './dates'

describe('toLocalYMD', () => {
  it('formats using local calendar fields, not UTC', () => {
    // 1 Jan 2026 00:30 local. toISOString() would roll this back to 2025-12-31
    // in any timezone east of UTC, which is the bug these helpers exist to avoid.
    expect(toLocalYMD(new Date(2026, 0, 1, 0, 30))).toBe('2026-01-01')
  })

  it('zero-pads month and day', () => {
    expect(toLocalYMD(new Date(2026, 2, 5))).toBe('2026-03-05')
  })

  it('never returns the previous day for a late-evening date', () => {
    expect(toLocalYMD(new Date(2026, 5, 15, 23, 59))).toBe('2026-06-15')
  })
})

describe('parseLocalYMD', () => {
  it('parses to local midnight', () => {
    const d = parseLocalYMD('2026-08-18')!
    expect(d.getFullYear()).toBe(2026)
    expect(d.getMonth()).toBe(7)
    expect(d.getDate()).toBe(18)
    expect(d.getHours()).toBe(0)
  })

  it('rejects malformed input', () => {
    expect(parseLocalYMD('18-08-2026')).toBeNull()
    expect(parseLocalYMD('2026-8-18')).toBeNull()
    expect(parseLocalYMD('')).toBeNull()
    expect(parseLocalYMD('nope')).toBeNull()
  })

  it('rejects calendar-invalid dates rather than rolling them over', () => {
    expect(parseLocalYMD('2026-02-30')).toBeNull()
    expect(parseLocalYMD('2026-13-01')).toBeNull()
  })

  it('round-trips with toLocalYMD', () => {
    expect(toLocalYMD(parseLocalYMD('2024-02-29')!)).toBe('2024-02-29')
  })
})

describe('yearsAgoYMD', () => {
  it('subtracts whole years from a fixed date', () => {
    expect(yearsAgoYMD(3, new Date(2026, 7, 18))).toBe('2023-08-18')
  })

  it('handles a leap day source', () => {
    // 29 Feb 2024 minus 1 year has no exact counterpart; must stay a valid date.
    const out = yearsAgoYMD(1, new Date(2024, 1, 29))
    expect(parseLocalYMD(out)).not.toBeNull()
  })
})

describe('isYearPreset', () => {
  it('matches an exact n-year window', () => {
    expect(isYearPreset(3, '2023-08-18', '2026-08-18')).toBe(true)
    expect(isYearPreset(1, '2025-08-18', '2026-08-18')).toBe(true)
  })

  it('tolerates a few days of leap jitter', () => {
    expect(isYearPreset(3, '2023-08-20', '2026-08-18')).toBe(true)
  })

  it('rejects a different span', () => {
    expect(isYearPreset(3, '2024-08-18', '2026-08-18')).toBe(false)
    expect(isYearPreset(1, '2023-08-18', '2026-08-18')).toBe(false)
  })

  it('rejects unparseable input', () => {
    expect(isYearPreset(3, 'nope', '2026-08-18')).toBe(false)
  })
})

describe('todayYMD', () => {
  it('agrees with toLocalYMD for the current date', () => {
    expect(todayYMD()).toBe(toLocalYMD(new Date()))
  })
})
