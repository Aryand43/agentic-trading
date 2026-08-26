import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TradeAuditTable } from './TradeAuditTable'
import type { TradeAuditRow } from '../types/pipeline'

const trades: TradeAuditRow[] = [
  {
    trade_id: 'a',
    ticker: 'AAPL',
    signal_date: '2024-01-02',
    signal_horizon: '5d',
    signal_value: 0.4,
    signal_side: 'buy',
    entry_date: '2024-01-03',
    entry_price: 10,
    exit_date: '2024-01-08',
    exit_price: 11,
    position_direction: 'long',
    exit_reason: 'horizon_end',
    net_pnl: 1,
    return: 0.1,
  },
  {
    trade_id: 'b',
    ticker: 'NVDA',
    signal_date: '2024-01-02',
    signal_horizon: '10d',
    signal_value: -0.5,
    signal_side: 'sell',
    entry_date: '2024-01-03',
    entry_price: 20,
    exit_date: '2024-01-06',
    exit_price: 18,
    position_direction: 'short',
    exit_reason: 'take_profit',
    net_pnl: 2,
    return: 0.1,
  },
]

describe('TradeAuditTable', () => {
  it('renders trade rows and filters by ticker', () => {
    render(<TradeAuditTable trades={trades} />)
    const table = screen.getByTestId('trade-audit-table')
    expect(table.textContent).toContain('AAPL')
    expect(table.textContent).toContain('NVDA')
    fireEvent.change(screen.getByLabelText('Filter ticker'), { target: { value: 'AAPL' } })
    expect(table.textContent).toContain('AAPL')
    expect(table.textContent).not.toContain('NVDA')
  })
})
