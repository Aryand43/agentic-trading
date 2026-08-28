"""Shared constants used by signals, risk, portfolio, backtest, and agents."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HORIZONS = ["1d", "3d", "5d", "10d", "15d", "1m", "3m"]

# Approximate trading-day window for each horizon, for anyone computing
# rolling windows (returns, volatility, etc.) over these horizons.
HORIZON_TRADING_DAYS = {
    "1d": 1,
    "3d": 3,
    "5d": 5,
    "10d": 10,
    "15d": 15,
    "1m": 21,
    "3m": 63,
}

# --- Risk Engine & Trading Variables ---

# Market structure constants
MINUTES_PER_TRADING_DAY = 390
TRADING_DAYS_PER_YEAR = 252

# Live desk: daily research history (cache-friendly, multi-horizon signals work).
# Intraday 1m remains available via explicit period/interval overrides.
TRADING = {
    "tickers": ["AAPL", "MSFT", "NVDA"],
    "period": "1y",
    "interval": "1d",
}

# Research mode: multi-year daily bars for backtests and agent loops
RESEARCH = {
    "tickers": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
        "COST", "NFLX", "AMD", "PEP", "ADBE", "CSCO", "INTC",
    ],
    "period": "5y",
    "interval": "1d",
    # Capital-curve baseline (Rui: SPX); QQQ remains available for regimes
    "benchmark": "SPY",
    "regime_benchmark": "QQQ",
    "cost_bps": 5.0,
    "initial_capital": 10_000.0,
    # Legacy 2-way fraction (still used as fallback when day windows too short)
    "train_frac": 0.7,
    # Rui train / val / test windows (trading days, chronological to as_of)
    "as_of": None,  # None → last bar in panel
    "train_days": 756,  # ~3y
    "val_days": 126,  # ~6m
    "test_days": 15,  # ~3w
    # Utility = w_hit * signal_hit + w_arr * tanh(ARR) style blend
    "utility_w_hit": 0.5,
    "utility_w_arr": 0.5,
    # Stagnation: plateau of utility over this many iters → complementary recon
    "stagnation_iters": 3,
    "rebalance_every": 5,  # trading days between portfolio rebalances
    "warmup_bars": 260,  # need ~1y history for long-horizon signals
    "take_profit_pct": 0.08,
    "stop_loss_pct": 0.04,
    "slippage_bps": 0.0,
    "side_mode": "long_short",
    "long_threshold": 0.05,
    "short_threshold": 0.05,
}

# Flag segments / risk rows with fewer than this many trading days.
MIN_SAMPLE_TRADING_DAYS = 120

# Persistent strategy catalog / leaderboard root
CATALOG_DIR = ROOT / "runs" / "catalog"

# Liquid NASDAQ-heavy universe for agent discovery runs
NASDAQ_UNIVERSE = list(RESEARCH["tickers"])

# Frozen paper-experiment protocol (used when the LLM planner is off or fails).
# test_days=63 is longer than RESEARCH["test_days"] (15) so tables are usable.
PAPER_PROTOCOL = {
    "tickers": list(NASDAQ_UNIVERSE),
    "period": "5y",
    "horizons": list(HORIZONS),
    "include_agent": True,
    "n_iterations": 2,
    "test_days": 63,
    "agent_horizons": ["10d"],
}

RISK = {
    "window_size": 60,  # (60 bars = 1 hour of 1-minute data)
    "confidence": 0.95,
    "estimation_days": 21,  # (21 days ensures statistical significance regardless of the forecast horizon)
    "ewma_lambda": 0.99,  # Added for dynamic variance decay (EWMA)
    # Daily research estimation window (bars of daily returns)
    "daily_estimation_days": 63,
}

# Disk layout for caches, reports, and agent runs
DATA_CACHE_DIR = ROOT / "data" / "cache"
REPORTS_DIR = ROOT / "reports"
RUNS_DIR = ROOT / "runs"
