"""Fetch market data and run signal + risk modules for portfolio construction.

Returns the dicts expected by ``construct_portfolio()`` in
``src/portfolio/construction.py``.

Live desk defaults to **daily** multi-month history (research-compatible):
signal lookbacks and yfinance reliability. Prefer cache over 1m intraday.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import HORIZONS, TRADING
from src.risk.engine.data_loader import fetch_market_data, fetch_research_prices
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
    # Zero overnight gaps only for *intraday* panels (many bars per calendar day).
    # For daily bars, every row is a new day — zeroing would wipe all returns.
    if len(log_returns) > 1:
        dates = pd.Series(
            [ts.date() if hasattr(ts, "date") else ts for ts in log_returns.index],
            index=log_returns.index,
        )
        bars_per_day = dates.groupby(dates).transform("count")
        if int(bars_per_day.max()) > 1:
            is_new_day = dates != dates.shift(1)
            log_returns[is_new_day] = 0.0
    return log_returns.dropna()


def _fetch_live_prices(tickers: list[str], provider: str) -> pd.DataFrame:
    """Daily-first live fetch with research cache fallback (never depend on 5d/1m alone)."""
    # 1) Explicit daily window matching TRADING defaults
    try:
        frame = fetch_market_data(
            tickers,
            provider=provider,
            mode="live",
            period=TRADING.get("period", "1y"),
            interval=TRADING.get("interval", "1d"),
            use_cache=True,
        )
        if frame is not None and not frame.empty:
            return frame
    except Exception:
        pass

    # 2) Research 1y/5y daily (reuses data/cache from backtests)
    for period in ("1y", "3y", "5y"):
        try:
            frame = fetch_research_prices(tickers, period=period, use_cache=True)
            if frame is not None and not frame.empty:
                return frame
        except Exception:
            continue

    # 3) Last-chance: generic research mode
    return fetch_market_data(tickers, provider=provider, mode="research", use_cache=True)


def load_pipeline_data(
    tickers: list[str] | None = None,
    provider: str = "yfinance",
    volatility_horizon: str = DEFAULT_VOLATILITY_HORIZON,
    portfolio_horizon: str = DEFAULT_PORTFOLIO_HORIZON,
    target_volatility: float = DEFAULT_TARGET_VOLATILITY,
) -> tuple[dict[str, dict[str, float]], dict[str, float], float, float]:
    """Returns (signals_by_ticker_horizon, volatilities_by_ticker, portfolio_volatility, target_volatility)."""
    tickers = tickers or list(TRADING["tickers"])
    prices = _normalize_prices(_fetch_live_prices(tickers, provider), tickers)
    # Align to available columns if some tickers failed
    tickers = [t for t in tickers if t in prices.columns]
    if not tickers:
        raise ValueError(
            "No price data for live snapshot. Run a Backtest once to fill data/cache/, "
            "or check network access to Yahoo Finance."
        )

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
