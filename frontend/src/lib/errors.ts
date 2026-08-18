/** Map raw API errors into short, actionable desk messages. */

export const DESK_VERSION = 'v0.7'

/** Signatures of server-side crashes that should never be shown verbatim. */
const INTERNAL_CRASH_PATTERNS = [
  'traceback (most recent call last)',
  'codec can',
  'unicodeencodeerror',
  'unicodedecodeerror',
  'keyerror',
  'attributeerror',
  'typeerror:',
  'indexerror',
  'zerodivisionerror',
  'nonetype',
]

function looksLikeInternalCrash(lower: string): boolean {
  return INTERNAL_CRASH_PATTERNS.some((p) => lower.includes(p))
}

export function formatDeskError(raw: string | null | undefined): string | null {
  if (!raw) return null
  const t = raw.trim()
  if (!t) return null

  const lower = t.toLowerCase()

  if (
    lower.includes('5d/1m') ||
    lower.includes('yfinance returned no data') ||
    lower.includes('failed to perform') ||
    lower.includes('could not resolve')
  ) {
    return (
      "Couldn't fetch prices from Yahoo. Switch to Backtest → Last 3y (uses daily + cache), " +
      'confirm the API is on :8000, then hard-restart frontend if you still see this old error.'
    )
  }

  if (
    lower.includes('failed to fetch') ||
    lower.includes('networkerror') ||
    lower.includes('load failed')
  ) {
    return "Can't reach the API. Start: uvicorn api.main:app --reload --port 8000"
  }

  if (lower.includes('start_date') && lower.includes('end_date')) {
    return 'Set both Start and End dates, or switch to a period string (1y / 3y / 5y).'
  }

  if (lower.includes('not enough price history')) {
    return `${t} Try a longer window (Last 3y / 5y) or fewer exotic tickers.`
  }

  // A server-side crash is not something the user can act on, and the raw text
  // (e.g. "'charmap' codec can't encode character '∈'") reads as if they
  // typed something wrong. Say what it is and keep the detail for the console.
  if (looksLikeInternalCrash(lower)) {
    return (
      'The API hit an internal error on this run — nothing is wrong with your inputs. ' +
      'Check the uvicorn console for the traceback. ' +
      `Detail: ${t.length > 160 ? `${t.slice(0, 160)}…` : t}`
    )
  }

  // Keep technical detail but strip noise
  if (t.length > 280) {
    return `${t.slice(0, 280)}…`
  }
  return t
}
