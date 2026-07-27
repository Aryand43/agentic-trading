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
