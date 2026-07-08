"""Shared constants used by signals, risk, and portfolio modules."""

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

# The fixed historical lookback window used to calculate standard deviation and covariance 

TRADING = {
    "tickers": ["AAPL", "MSFT", "NVDA"],
    "period": "5d",
    "interval": "1m"
}

RISK = {
    "window_size": 60,  # (60 bars = 1 hour of 1-minute data)
    "confidence": 0.95,
    "estimation_days": 21  # (21 days ensures statistical significance regardless of the forecast horizon)
}
