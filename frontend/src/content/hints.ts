/** Short hover blurbs for dashboard features. */
export const HINTS = {
  tickers: 'Stock symbols to trade. Comma- or space-separated (e.g. AAPL, MSFT).',
  maxPosition:
    'Cap on how big any single name can be (as a fraction of the book). Stops one stock from dominating.',
  grossExposure: 'Sum of absolute weights after sizing. 1.0 ≈ full capital; higher allows leverage.',
  runPipeline:
    'Fetches live prices, scores each ticker across 7 horizons, measures risk, then sizes long/short weights.',
  conviction:
    'One blended buy/sell score per ticker (−1 to +1). Horizons that disagree damp the score toward flat.',
  weights:
    'Final portfolio allocation. Positive = long, negative = short. Sized down for jumpy names and scaled to target risk.',
  horizonSignals:
    'Raw signal from each holding-period strategy before blending. Teal leans buy, rose leans sell.',
  portfolioVol: 'How jumpy the equal-weight basket is right now — used to scale the whole book.',
  targetVol: 'Risk level we aim for. If the book is too wild, positions get shrunk; if too calm, grown.',
  equityCurve:
    'Simulated capital path: multi-horizon portfolio vs classic TA baselines over your chosen window.',
  backtest:
    'Walks daily history: rebalance from blended signals + risk, chart capital, report Sharpe / drawdown / hit rate.',
  modeBacktest: 'Multi-year capital curve, baselines, and segmented performance — Rui demo path.',
  modeLive: 'Point-in-time pipeline snapshot (conviction, weights, horizon votes).',
  modeAgent:
    'One horizon agent loop: hypothesize → backtest → insights → next hypothesis (artifacts under runs/).',
  dateStart:
    'First calendar day of the research window (inclusive). After a run, snaps to the first session used.',
  dateEnd:
    'Last calendar day of the research window (inclusive). After a run, snaps to the last session used.',
  period: 'Relative yfinance window when calendar dates are off (e.g. 3y).',
  initialCapital: 'Starting portfolio value for equity curve and metrics (default $10,000).',
  agentHorizon: 'Which holding-period strategy agent to run (one horizon = one agent).',
  agentIters: 'Number of discovery loops (1–5). More iters → longer runtime.',
  segments: 'Where the strategy wins/loses: bull vs bear, vol buckets, industry groups.',
  agentHistory: 'Each hypothesis iteration with train/test Sharpe and analytical insights.',
  windowStrip: 'Actual data range used for this run after download and filters.',
  tickerVol: (ticker: string) =>
    `How volatile ${ticker} is. Higher vol → smaller position for the same conviction.`,
  horizons: {
    '1d': '1-day signal — VWAP breakout / short-term momentum.',
    '3d': '3-day signal — ConnorsRSI mean reversion.',
    '5d': '5-day signal — Bollinger band volatility squeeze.',
    '10d': '10-day signal — SMA(10)/SMA(50) momentum + RSI.',
    '15d': '15-day signal — residual / overreaction reversal proxy.',
    '1m': '1-month signal — short-term reversal proxy.',
    '3m': '3-month signal — Jegadeesh–Titman momentum (skip last month).',
  } as Record<string, string>,
} as const
