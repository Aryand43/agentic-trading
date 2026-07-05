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
