/** Shared number/label formatting. Kept out of components so it stays testable. */

export function fmtPct(x: number | null | undefined, digits = 1): string {
  if (x == null || Number.isNaN(x)) return '—'
  return `${(x * 100).toFixed(digits)}%`
}

export function fmtSigned(x: number | null | undefined, digits = 2): string {
  if (x == null || Number.isNaN(x)) return '—'
  const s = x.toFixed(digits)
  return x > 0 ? `+${s}` : s
}

export function fmtNum(x: number | null | undefined, digits = 2): string {
  if (x == null || Number.isNaN(x)) return '—'
  return x.toFixed(digits)
}

export function fmtMoney(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return '—'
  return `$${Math.round(x).toLocaleString()}`
}

/** `buy_and_hold` -> `Buy and hold`. Used for baseline + segment labels. */
export function humanize(name: string): string {
  const spaced = name.replace(/[_-]+/g, ' ').trim()
  if (!spaced) return ''
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** Tone for a signed value, matching the palette used across the desk. */
export function toneOf(x: number | null | undefined): 'up' | 'down' | 'flat' {
  if (x == null || Number.isNaN(x) || x === 0) return 'flat'
  return x > 0 ? 'up' : 'down'
}

export const TONE_TEXT: Record<'up' | 'down' | 'flat', string> = {
  up: 'text-teal',
  down: 'text-rose',
  flat: 'text-muted',
}

export function parseTickers(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
}
