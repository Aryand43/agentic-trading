export type RunMode = 'backtest' | 'live' | 'agent'

export type RunRequest = {
  tickers?: string[] | null
  max_position?: number
  gross_exposure?: number
  target_volatility?: number | null
}

export type PipelineResult = {
  tickers: string[]
  horizons: string[]
  signals: Record<string, Record<string, number>>
  conviction: Record<string, number>
  volatilities: Record<string, number>
  portfolio_volatility: number
  target_volatility: number
  weights: Record<string, number>
}

export type EquityPoint = {
  date: string
  equity: number
  series?: string
}

export type MetricsBlock = {
  total_return: number
  annualized_return: number
  sharpe: number
  max_drawdown: number
  hit_rate: number
  signal_hit_rate?: number
  utility?: number
  turnover: number
  n_days: number
  final_equity: number
  start_equity: number
}

export type WindowInfo = {
  start: string
  end: string
  n_days: number
  period_used?: string | null
}

export type SplitWindow = {
  start?: string | null
  end?: string | null
  n_days?: number | null
}

export type ResearchWindows = {
  as_of?: string | null
  train?: SplitWindow | null
  val?: SplitWindow | null
  test?: SplitWindow | null
}

export type BacktestRequest = {
  tickers?: string[] | null
  period?: string
  start_date?: string | null
  end_date?: string | null
  initial_capital?: number
  max_position?: number
  gross_exposure?: number
  target_volatility?: number
  include_baselines?: boolean
  include_segments?: boolean
  baselines?: string[]
}

export type BacktestResult = {
  tickers: string[]
  initial_capital: number
  window: WindowInfo
  research_windows?: ResearchWindows | null
  metrics: MetricsBlock
  baselines: Record<string, MetricsBlock>
  equity_curve: EquityPoint[]
  baseline_curves: Record<string, EquityPoint[]>
  segments: {
    regime?: Record<string, MetricsBlock | Record<string, unknown>>
    volatility?: Record<string, MetricsBlock | Record<string, unknown>>
    industry?: Record<string, MetricsBlock | Record<string, unknown>>
  }
  portfolios?: Record<string, unknown>
}

export type AgentRequest = {
  tickers?: string[] | null
  period?: string
  start_date?: string | null
  end_date?: string | null
  horizon?: string
  n_iterations?: number
  initial_capital?: number
  seed_baselines?: boolean
}

export type AgentIteration = {
  iteration: number
  hypothesis: string
  template: string
  params: Record<string, number>
  name?: string
  train_sharpe: number | null
  val_sharpe?: number | null
  test_sharpe: number | null
  utility?: number | null
  insights: string
  code_hash: string
  portfolios?: Record<string, unknown>
  test_summary?: Record<string, number>
}

export type LeaderboardRow = {
  iteration: number
  name: string
  template: string
  test_utility: number | null
  test_sharpe: number | null
  test_hit: number | null
  code_hash: string
}

export type AgentResult = {
  horizon: string
  window: WindowInfo
  research_windows?: ResearchWindows | null
  tickers: string[]
  run_dir: string
  best_iteration: number
  best_test_sharpe: number
  best_test_utility?: number
  iterations: AgentIteration[]
  leaderboard?: LeaderboardRow[]
  utility_curve?: { iteration: number; utility: number; name?: string }[]
  catalog_path?: string
}

export const HORIZONS = ['1d', '3d', '5d', '10d', '15d', '1m', '3m'] as const

export const NASDAQ_SAMPLE =
  'AAPL, MSFT, NVDA, AMZN, GOOGL, META'
