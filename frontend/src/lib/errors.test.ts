import { describe, expect, it } from 'vitest'
import { formatDeskError } from './errors'

describe('formatDeskError', () => {
  it('passes through empty input', () => {
    expect(formatDeskError(null)).toBeNull()
    expect(formatDeskError(undefined)).toBeNull()
    expect(formatDeskError('   ')).toBeNull()
  })

  it('explains an unreachable API', () => {
    expect(formatDeskError('TypeError: Failed to fetch')).toContain('uvicorn')
  })

  it('explains a Yahoo fetch failure', () => {
    expect(formatDeskError('yfinance returned no data')).toContain("Couldn't fetch prices")
  })

  it('explains a half-filled date pair', () => {
    const msg = formatDeskError('Provide both start_date and end_date, or neither.')!
    expect(msg).toContain('Set both Start and End dates')
  })

  it('keeps the short-history message and adds a suggestion', () => {
    const msg = formatDeskError('Not enough price history in the selected window.')!
    expect(msg).toContain('Not enough price history')
    expect(msg).toContain('longer window')
  })

  it('does not blame the user for a server-side crash', () => {
    const raw = "'charmap' codec can't encode character '\\u2208' in position 475"
    const msg = formatDeskError(raw)!
    expect(msg).toContain('internal error')
    expect(msg).toContain('nothing is wrong with your inputs')
    // Detail is preserved for whoever is debugging.
    expect(msg).toContain('charmap')
  })

  it('recognises a python traceback', () => {
    expect(formatDeskError('Traceback (most recent call last): ...')).toContain('internal error')
  })

  it('recognises a NoneType attribute error', () => {
    const msg = formatDeskError("AttributeError: 'NoneType' object has no attribute 'index'")!
    expect(msg).toContain('internal error')
  })

  it('truncates a very long unrecognised message', () => {
    const msg = formatDeskError('x'.repeat(400))!
    expect(msg.length).toBeLessThanOrEqual(281)
    expect(msg.endsWith('…')).toBe(true)
  })

  it('returns a short unrecognised message unchanged', () => {
    expect(formatDeskError('Unknown horizon: 7d')).toBe('Unknown horizon: 7d')
  })
})
