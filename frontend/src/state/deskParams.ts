/** All research-desk form state in one shape.
 *
 * Previously these lived as ~15 separate `useState` calls in App.tsx, each
 * threaded into ControlPanel as a value + setter pair (30 props). Adding one
 * control meant three coordinated edits with no type error if you missed one.
 */
import { todayYMD, yearsAgoYMD } from '../lib/dates'
import type { RunMode, WindowInfo } from '../types/pipeline'

export type DeskParams = {
  mode: RunMode
  tickersInput: string
  maxPosition: number
  grossExposure: number
  targetVolatility: number
  useDates: boolean
  startDate: string
  endDate: string
  period: string
  initialCapital: number
  includeBaselines: boolean
  includeSegments: boolean
  horizon: string
  iterations: number
}

export const INITIAL_PARAMS: DeskParams = {
  mode: 'backtest',
  tickersInput: 'AAPL, MSFT, NVDA',
  maxPosition: 0.15,
  grossExposure: 1.0,
  targetVolatility: 0.15,
  useDates: true,
  startDate: yearsAgoYMD(3),
  endDate: todayYMD(),
  period: '3y',
  initialCapital: 10_000,
  includeBaselines: true,
  includeSegments: true,
  horizon: '10d',
  iterations: 2,
}

export type DeskAction =
  | { type: 'set'; patch: Partial<DeskParams> }
  | { type: 'applyPreset'; years: number }
  | { type: 'snapToWindow'; window: WindowInfo }

export function deskReducer(state: DeskParams, action: DeskAction): DeskParams {
  switch (action.type) {
    case 'set':
      return { ...state, ...action.patch }
    case 'applyPreset':
      return {
        ...state,
        useDates: true,
        startDate: yearsAgoYMD(action.years),
        endDate: todayYMD(),
        period: `${action.years}y`,
      }
    case 'snapToWindow':
      return {
        ...state,
        useDates: true,
        startDate: action.window.start,
        endDate: action.window.end,
      }
    default:
      return state
  }
}

/** Date/period fields in the shape the API expects. */
export function windowFields(p: DeskParams) {
  return p.useDates
    ? { start_date: p.startDate, end_date: p.endDate, period: p.period || '3y' }
    : { start_date: null, end_date: null, period: p.period }
}
