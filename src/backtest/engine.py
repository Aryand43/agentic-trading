"""Point-in-time single-name and multi-name signal backtester (daily bars).

Walks history day-by-day, scores each ticker with only past prices (no lookahead),
maps score → signed position, applies simple transaction costs, accumulates PnL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from src.config import RESEARCH
from src.signals.strategies import get_signal

# signal(prices_so_far: pd.Series) -> float in [-1, 1]
SignalFn = Callable[[pd.Series], float]


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series  # aggregate gross signed exposure (equal-weight average of scores)
    per_ticker_positions: pd.DataFrame = field(default_factory=pd.DataFrame)
    per_ticker_returns: pd.DataFrame = field(default_factory=pd.DataFrame)
    prices: pd.DataFrame = field(default_factory=pd.DataFrame)
    label: str = ""
    meta: dict = field(default_factory=dict)


def _default_signal_fn(horizon: str) -> SignalFn:
    def _fn(prices: pd.Series) -> float:
        return get_signal("", horizon, prices)

    return _fn


def run_signal_backtest(
    prices: pd.DataFrame,
    *,
    signal_fn: SignalFn | None = None,
    horizon: str = "10d",
    initial_capital: float | None = None,
    cost_bps: float | None = None,
    warmup: int | None = None,
    rebalance_every: int = 1,
    label: str = "",
) -> BacktestResult:
    """Backtest a signal function over a multi-ticker Close panel.

    Each rebalance day the strategy is scored per ticker using prices[:t+1].
    Position for each name = score (long/short, |w| <= 1). Cross-sectional
    weights are equal-dollar across names (each name gets 1/N of capital times score).
    Between rebalances, positions are held constant (no mark-to-weight drift rebalance
    of cash — dollar exposure floats with price, simple model).
    """
    if prices is None or prices.empty:
        raise ValueError("prices panel is empty")

    prices = prices.sort_index().astype(float)
    tickers = list(prices.columns)
    n = len(tickers)
    signal_fn = signal_fn or _default_signal_fn(horizon)
    initial_capital = float(initial_capital if initial_capital is not None else RESEARCH["initial_capital"])
    cost_bps = float(cost_bps if cost_bps is not None else RESEARCH["cost_bps"])
    warmup = int(warmup if warmup is not None else RESEARCH["warmup_bars"])
    cost_rate = cost_bps / 10_000.0

    dates = list(prices.index)
    if len(dates) <= warmup + 2:
        raise ValueError(
            f"Need more history than warmup ({warmup}); only have {len(dates)} bars."
        )

    pos = np.zeros(n)  # target weight per ticker (sum abs can exceed 1 if scores are all 1 — normalize)
    equity_vals: list[float] = []
    ret_vals: list[float] = []
    pos_vals: list[float] = []
    pos_matrix: list[np.ndarray] = []
    ret_matrix: list[np.ndarray] = []
    equity = initial_capital
    equity_index: list = []

    for i, dt in enumerate(dates):
        if i == 0:
            continue

        day_ret = prices.iloc[i] / prices.iloc[i - 1] - 1.0
        day_ret = day_ret.replace([np.inf, -np.inf], np.nan).fillna(0.0).values

        # PnL from yesterday's positions
        asset_pnl = pos * day_ret
        port_ret = float(np.nansum(asset_pnl))
        equity *= 1.0 + port_ret

        # Rebalance decision after close on day i (signal uses data through i)
        if i >= warmup and (i - warmup) % rebalance_every == 0:
            scores = np.zeros(n)
            for j, ticker in enumerate(tickers):
                hist = prices[ticker].iloc[: i + 1].dropna()
                try:
                    scores[j] = float(np.clip(signal_fn(hist), -1.0, 1.0))
                except Exception:
                    scores[j] = 0.0

            # Equal risk budget: each name may take ±1/N of notional
            new_pos = scores / n
            turnover = float(np.abs(new_pos - pos).sum())
            equity *= 1.0 - turnover * cost_rate
            pos = new_pos

        equity_vals.append(equity)
        ret_vals.append(port_ret)
        pos_vals.append(float(pos.sum()))
        pos_matrix.append(pos.copy())
        ret_matrix.append(asset_pnl.copy())
        equity_index.append(dt)

    idx = pd.DatetimeIndex(equity_index)
    return BacktestResult(
        equity=pd.Series(equity_vals, index=idx, name="equity"),
        returns=pd.Series(ret_vals, index=idx, name="returns"),
        positions=pd.Series(pos_vals, index=idx, name="net_exposure"),
        per_ticker_positions=pd.DataFrame(pos_matrix, index=idx, columns=tickers),
        per_ticker_returns=pd.DataFrame(ret_matrix, index=idx, columns=tickers),
        prices=prices,
        label=label or horizon,
        meta={
            "horizon": horizon,
            "initial_capital": initial_capital,
            "cost_bps": cost_bps,
            "warmup": warmup,
            "rebalance_every": rebalance_every,
            "tickers": tickers,
        },
    )
