import { describe, expect, it } from 'vitest'
import { buildSegmentGroups, isEmptySegment } from './segments'
import type { MetricsBlock } from '../types/pipeline'

function metrics(over: Partial<MetricsBlock> = {}): MetricsBlock {
  return {
    total_return: 0.1,
    annualized_return: 0.05,
    sharpe: 0.5,
    max_drawdown: -0.1,
    hit_rate: 0.52,
    signal_hit_rate: 0.52,
    utility: 0.5,
    turnover: 0.01,
    n_days: 750,
    final_equity: 11000,
    start_equity: 10000,
    ...over,
  }
}

/** Shaped like a real /api/backtest response. */
const PAYLOAD = {
  regime: {
    bull: metrics({ sharpe: -0.601, total_return: -0.2103, hit_rate: 0.4786 }),
    bear: metrics({ sharpe: 0.416, total_return: 0.0564, hit_rate: 0.5 }),
    label_counts: { bull: 624, bear: 86, unknown: 40 },
  },
  volatility: {
    low: metrics({ n_days: 1, sharpe: 0, total_return: 0, hit_rate: 0 }),
    mid: metrics({ sharpe: 0.367 }),
    high: metrics({ sharpe: -0.707 }),
  },
  industry: {
    Technology: metrics({ sharpe: -0.408 }),
    _ticker_sector_map: { AAPL: 'Technology' },
  },
}

describe('isEmptySegment', () => {
  it('treats the backend n_days=1 sentinel as empty, not as one day of data', () => {
    expect(isEmptySegment(metrics({ n_days: 1 }))).toBe(true)
    expect(isEmptySegment(metrics({ n_days: 750 }))).toBe(false)
  })
})

describe('buildSegmentGroups', () => {
  const groups = buildSegmentGroups(PAYLOAD)

  it('returns the three groups in a stable order', () => {
    expect(groups.map((g) => g.key)).toEqual(['regime', 'volatility', 'industry'])
  })

  it('attaches real day counts to regime rows from label_counts', () => {
    const regime = groups.find((g) => g.key === 'regime')!
    expect(regime.hasCounts).toBe(true)
    expect(regime.rows.map((r) => [r.key, r.days])).toEqual([
      ['bull', 624],
      ['bear', 86],
    ])
  })

  it('computes share against every labelled day, including unreported buckets', () => {
    const regime = groups.find((g) => g.key === 'regime')!
    const bull = regime.rows.find((r) => r.key === 'bull')!
    // 624 / (624 + 86 + 40) = 0.832, NOT 624/710
    expect(bull.share).toBeCloseTo(624 / 750, 5)
  })

  it('reports days that fell outside the shown rows', () => {
    const regime = groups.find((g) => g.key === 'regime')!
    expect(regime.unclassifiedDays).toBe(40)
  })

  it('flags a small segment as thin', () => {
    const regime = groups.find((g) => g.key === 'regime')!
    expect(regime.rows.find((r) => r.key === 'bull')!.status).toBe('ok')
    expect(regime.rows.find((r) => r.key === 'bear')!.status).toBe('thin')
  })

  it('flags the sentinel volatility bucket as empty rather than as zeros', () => {
    const vol = groups.find((g) => g.key === 'volatility')!
    expect(vol.rows.find((r) => r.key === 'low')!.status).toBe('empty')
    expect(vol.rows.find((r) => r.key === 'mid')!.status).toBe('ok')
  })

  it('does not invent day counts for groups that carry none', () => {
    const vol = groups.find((g) => g.key === 'volatility')!
    expect(vol.hasCounts).toBe(false)
    expect(vol.rows.every((r) => r.days === null && r.share === null)).toBe(true)
  })

  it('drops the private _ticker_sector_map entry', () => {
    const industry = groups.find((g) => g.key === 'industry')!
    expect(industry.rows.map((r) => r.key)).toEqual(['Technology'])
  })

  it('labels time splits and holdings splits differently', () => {
    expect(groups.find((g) => g.key === 'regime')!.basis).toBe('time')
    expect(groups.find((g) => g.key === 'industry')!.basis).toBe('holdings')
  })

  it('renames raw bucket keys to readable labels', () => {
    const vol = groups.find((g) => g.key === 'volatility')!
    expect(vol.rows.map((r) => r.label)).toEqual(['Calm', 'Normal', 'Turbulent'])
  })

  it('omits groups with no rows instead of leaving a gap', () => {
    expect(buildSegmentGroups({ regime: PAYLOAD.regime })).toHaveLength(1)
    expect(buildSegmentGroups({})).toHaveLength(0)
  })

  it('survives a payload with only the private key', () => {
    const g = buildSegmentGroups({ industry: { _ticker_sector_map: {} } })
    expect(g).toHaveLength(0)
  })
})
