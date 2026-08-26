import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { EquityChart } from './EquityChart'
import type { TradeAuditRow } from '../types/pipeline'

vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children?: ReactNode }) => (
      <div style={{ width: 800, height: 320 }}>{children}</div>
    ),
  }
})

const trades: TradeAuditRow[] = [
  {
    trade_id: 't1',
    ticker: 'AAPL',
    signal_date: '2024-01-02',
    signal_horizon: '5d',
    signal_value: 0.8,
    signal_side: 'buy',
    entry_date: '2024-01-03',
    entry_price: 100,
    exit_date: '2024-01-08',
    exit_price: 108,
    position_direction: 'long',
    exit_reason: 'take_profit',
    net_pnl: 80,
    return: 0.08,
  },
  {
    trade_id: 't2',
    ticker: 'MSFT',
    signal_date: '2024-01-02',
    signal_horizon: '5d',
    signal_value: -0.7,
    signal_side: 'sell',
    entry_date: '2024-01-03',
    entry_price: 200,
    exit_date: '2024-01-08',
    exit_price: 190,
    position_direction: 'short',
    exit_reason: 'stop_loss',
    net_pnl: -10,
    return: -0.05,
  },
]

describe('EquityChart', () => {
  it('renders buy and sell markers from trades', () => {
    const { container } = render(
      <EquityChart
        equityCurve={[
          { date: '2024-01-03', equity: 10000, series: 'strategy' },
          { date: '2024-01-08', equity: 10100, series: 'strategy' },
        ]}
        initialCapital={10000}
        trades={trades}
      />,
    )
    expect(container.querySelector('[data-testid="trade-markers"]')?.getAttribute('data-buy')).toBe(
      'true',
    )
    expect(container.querySelector('[data-testid="trade-markers"]')?.getAttribute('data-sell')).toBe(
      'true',
    )
  })
})
