"""Risk and volatility signals — owned by Anish and team.

Two levels, both indexed by the same horizons as the trading strategies:
  1. Single-stock volatility: how much one ticker's returns spread out.
  2. Portfolio-level risk: how much a weighted basket of tickers moves,
     which is not just the average of individual volatilities since stocks
     can move together (correlated) or offset each other.
"""

import pandas as pd

from src.config import HORIZONS


def stock_volatility(ticker: str, horizon: str, prices: pd.Series) -> float:
    """TODO(Anish): standard deviation of `ticker` returns over `horizon`."""
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {horizon}")
    raise NotImplementedError("stock_volatility not yet implemented")


def stock_var(ticker: str, horizon: str, prices: pd.Series, confidence: float = 0.95) -> float:
    """TODO(Anish): Value-at-Risk for `ticker` over `horizon`."""
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {horizon}")
    raise NotImplementedError("stock_var not yet implemented")


def portfolio_volatility(weights: dict[str, float], horizon: str, returns: pd.DataFrame) -> float:
    """TODO(Anish): portfolio-level volatility for `weights` over `horizon`,
    accounting for covariance between tickers (not just weighted-average of
    single-stock volatilities).
    """
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {horizon}")
    raise NotImplementedError("portfolio_volatility not yet implemented")


def portfolio_var(weights: dict[str, float], horizon: str, returns: pd.DataFrame, confidence: float = 0.95) -> float:
    """TODO(Anish): portfolio-level Value-at-Risk for `weights` over `horizon`."""
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {horizon}")
    raise NotImplementedError("portfolio_var not yet implemented")
