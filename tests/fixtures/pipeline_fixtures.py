"""Fixed pipeline inputs for unit tests (not used by the live demo)."""


def load_fake_data() -> tuple[dict[str, dict[str, float]], dict[str, float], float, float]:
    """Returns (signals_by_ticker_horizon, volatilities_by_ticker, portfolio_volatility, target_volatility)."""

    # Per ticker, per horizon, a score in [-1, 1].
    # AAPL is a deliberate conflict case: short horizons say buy, long horizons say sell.
    signals_by_ticker_horizon = {
        "AAPL": {"1d": 0.6, "3d": 0.5, "5d": 0.3, "10d": -0.2, "15d": -0.4, "1m": -0.5, "3m": -0.6},
        "MSFT": {"1d": 0.4, "3d": 0.5, "5d": 0.5, "10d": 0.6, "15d": 0.5, "1m": 0.4, "3m": 0.3},
        "TSLA": {"1d": -0.7, "3d": -0.6, "5d": -0.5, "10d": -0.4, "15d": -0.3, "1m": -0.2, "3m": -0.1},
    }

    volatilities_by_ticker = {
        "AAPL": 0.018,
        "MSFT": 0.015,
        "TSLA": 0.045,
    }

    portfolio_volatility = 0.022
    target_volatility = 0.015

    return signals_by_ticker_horizon, volatilities_by_ticker, portfolio_volatility, target_volatility
