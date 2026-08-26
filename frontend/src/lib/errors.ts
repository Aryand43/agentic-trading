/** Map raw API errors into short, actionable desk messages. */
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
      "confirm the API is on :8000, then hard-restart frontend if you still see this old error."
    )
  }

  if (lower.includes('failed to fetch') || lower.includes('networkerror') || lower.includes('load failed')) {
    return "Can't reach the API. Start: uvicorn api.main:app --reload --port 8000"
  }

  if (lower.includes('start_date') && lower.includes('end_date')) {
    return 'Set both Start and End dates, or switch to a period string (1y / 3y / 5y).'
  }

  if (lower.includes('not enough price history')) {
    return `${t} Try a longer window (Last 3y / 5y) or fewer exotic tickers.`
  }

  // Keep technical detail but strip noise
  if (t.length > 280) {
    return `${t.slice(0, 280)}…`
  }
  return t
}

export const DESK_VERSION = 'v0.7'
