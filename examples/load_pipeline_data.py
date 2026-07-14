"""Fetch market data and run signal + risk modules for portfolio construction.

Returns the dicts expected by ``construct_portfolio()`` in
``src/portfolio/construction.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import HORIZONS, TRADING
from src.risk.engine.data_loader import fetch_market_data
from src.risk.volatility import portfolio_volatility, stock_volatility
from src.signals.strategies import get_signal

DEFAULT_VOLATILITY_HORIZON = "1d"
DEFAULT_PORTFOLIO_HORIZON = "1d"
DEFAULT_TARGET_VOLATILITY = 0.015


def _normalize_prices(raw: pd.Series | pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if isinstance(raw, pd.Series):
        return raw.to_frame(name=tickers[0])
    return raw


def _prepare_returns(prices: pd.DataFrame) -> pd.DataFrame:
    log_returns = np.log(prices / prices.shift(1))
    dates = pd.Series(log_returns.index.date, index=log_returns.index)
    is_new_day = dates != dates.shift(1)
    log_returns[is_new_day] = 0.0
    return log_returns.dropna()


def load_pipeline_data(
    tickers: list[str] | None = None,
    provider: str = "yfinance",
    volatility_horizon: str = DEFAULT_VOLATILITY_HORIZON,
    portfolio_horizon: str = DEFAULT_PORTFOLIO_HORIZON,
    target_volatility: float = DEFAULT_TARGET_VOLATILITY,
) -> tuple[dict[str, dict[str, float]], dict[str, float], float, float]:
    """Returns (signals_by_ticker_horizon, volatilities_by_ticker, portfolio_volatility, target_volatility)."""
    tickers = tickers or TRADING["tickers"]
    prices = _normalize_prices(fetch_market_data(tickers, provider=provider), tickers)
    returns = _prepare_returns(prices)

    signals_by_ticker_horizon = {
        ticker: {
            horizon: get_signal(ticker, horizon, prices[ticker].dropna())
            for horizon in HORIZONS
        }
        for ticker in tickers
    }

    volatilities_by_ticker = {
        ticker: stock_volatility(ticker, volatility_horizon, returns[ticker])
        for ticker in tickers
    }

    equal_weights = {ticker: 1.0 / len(tickers) for ticker in tickers}
    port_vol = portfolio_volatility(equal_weights, portfolio_horizon, returns)

    return signals_by_ticker_horizon, volatilities_by_ticker, port_vol, target_volatility
