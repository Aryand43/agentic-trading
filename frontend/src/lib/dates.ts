/** Calendar helpers that stay on the user's local day (never UTC via toISOString). */

export function toLocalYMD(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Parse `YYYY-MM-DD` as local midnight (not UTC). */
export function parseLocalYMD(ymd: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ymd.trim())
  if (!m) return null
  const y = Number(m[1])
  const mo = Number(m[2])
  const d = Number(m[3])
  const dt = new Date(y, mo - 1, d)
  if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) {
    return null
  }
  return dt
}

export function yearsAgoYMD(years: number, from: Date = new Date()): string {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate())
  d.setFullYear(d.getFullYear() - years)
  return toLocalYMD(d)
}

export function todayYMD(): string {
  return toLocalYMD(new Date())
}

/** True when start ≈ end − years (within 4 calendar days for leap jitter). */
export function isYearPreset(years: number, startDate: string, endDate: string): boolean {
  const end = parseLocalYMD(endDate)
  const start = parseLocalYMD(startDate)
  if (!end || !start) return false
  const expected = new Date(end.getFullYear(), end.getMonth(), end.getDate())
  expected.setFullYear(expected.getFullYear() - years)
  const delta = Math.abs(start.getTime() - expected.getTime())
  return delta < 4 * 86400000
}
