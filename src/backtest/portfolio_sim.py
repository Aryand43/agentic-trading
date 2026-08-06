"""Historical multi-horizon portfolio rebalance simulation.

Uses the live construction path (blend horizons → inv-vol weights → target vol)
on rolling daily history to produce an equity curve from initial capital
(default $10k over multi-year daily bars).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult
from src.config import HORIZONS, RESEARCH
from src.portfolio.construction import combine_horizon_signals, construct_portfolio
from src.signals.strategies import get_signal


def _daily_vol(returns: pd.Series, window: int = 63) -> float:
    """Annualized daily-return volatility estimate for sizing."""
    clean = returns.dropna()
    if len(clean) < 5:
        return 0.20
    w = min(window, len(clean))
    return float(clean.tail(w).std() * np.sqrt(252))


def _abs_portfolio_vol(weights: dict[str, float], returns: pd.DataFrame, window: int = 63) -> float:
    """Portfolio vol allowing long/short: sqrt(w' Sigma w) on daily returns."""
    tickers = [t for t in weights if t in returns.columns]
    if not tickers:
        return 0.0
    w = np.array([weights[t] for t in tickers], dtype=float)
    ret = returns[tickers].dropna(how="all").fillna(0.0)
    if len(ret) < 5:
        return float(np.sqrt(np.dot(w, w)) * 0.20)
    sample = ret.tail(min(window, len(ret)))
    cov = sample.cov().values
    var = float(np.dot(w, np.dot(cov, w)))
    return float(np.sqrt(max(var, 0.0)) * np.sqrt(252))


@dataclass
class PortfolioSimResult(BacktestResult):
    weights_history: pd.DataFrame = field(default_factory=pd.DataFrame)
    conviction_history: pd.DataFrame = field(default_factory=pd.DataFrame)


def run_portfolio_backtest(
    prices: pd.DataFrame,
    *,
    initial_capital: float | None = None,
    cost_bps: float | None = None,
    warmup: int | None = None,
    rebalance_every: int | None = None,
    max_position: float = 0.15,
    gross_exposure: float = 1.0,
    target_volatility: float = 0.15,
    max_leverage: float = 2.0,
    horizons: list[str] | None = None,
    label: str = "multi_horizon_portfolio",
) -> PortfolioSimResult:
    """Rebalance a multi-horizon risk-aware portfolio over daily history."""
    prices = prices.sort_index().astype(float)
    tickers = list(prices.columns)
    horizons = horizons or list(HORIZONS)
    initial_capital = float(initial_capital if initial_capital is not None else RESEARCH["initial_capital"])
    cost_bps = float(cost_bps if cost_bps is not None else RESEARCH["cost_bps"])
    warmup = int(warmup if warmup is not None else RESEARCH["warmup_bars"])
    rebalance_every = int(rebalance_every if rebalance_every is not None else RESEARCH["rebalance_every"])
    cost_rate = cost_bps / 10_000.0

    dates = list(prices.index)
    if len(dates) <= warmup + 2:
        raise ValueError(f"Need more history than warmup ({warmup}); only have {len(dates)} bars.")

    log_ret = np.log(prices / prices.shift(1)).replace([np.inf, -np.inf], np.nan)
    simple_ret = prices.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)

    weights = {t: 0.0 for t in tickers}
    w_array = np.zeros(len(tickers))
    equity = initial_capital
    equity_vals: list[float] = []
    ret_vals: list[float] = []
    pos_vals: list[float] = []
    pos_matrix: list[np.ndarray] = []
    ret_matrix: list[np.ndarray] = []
    w_hist: list[dict[str, float]] = []
    conv_hist: list[dict[str, float]] = []
    equity_index: list = []

    for i, dt in enumerate(dates):
        if i == 0:
            continue

        day_ret = simple_ret.iloc[i].values
        asset_pnl = w_array * day_ret
        port_ret = float(np.nansum(asset_pnl))
        equity *= 1.0 + port_ret

        if i >= warmup and (i - warmup) % rebalance_every == 0:
            hist_prices = prices.iloc[: i + 1]
            hist_returns = log_ret.iloc[: i + 1].fillna(0.0)

            signals: dict[str, dict[str, float]] = {}
            vols: dict[str, float] = {}
            for t in tickers:
                series = hist_prices[t].dropna()
                signals[t] = {
                    h: get_signal(t, h, series) for h in horizons
                }
                vols[t] = _daily_vol(hist_returns[t])

            conviction = {
                t: combine_horizon_signals(signals[t]) for t in tickers
            }

            # Preliminary inv-vol weights (no target scale)
            prelim = construct_portfolio(
                signals,
                vols,
                max_position=max_position,
                gross_exposure=gross_exposure,
            )
            port_vol = _abs_portfolio_vol(prelim, hist_returns)
            # Annualized target — scale if far from target
            new_weights = construct_portfolio(
                signals,
                vols,
                max_position=max_position,
                gross_exposure=gross_exposure,
                portfolio_volatility=port_vol if port_vol > 0 else None,
                target_volatility=target_volatility if port_vol > 0 else None,
                max_leverage=max_leverage,
            )

            new_arr = np.array([new_weights.get(t, 0.0) for t in tickers], dtype=float)
            turnover = float(np.abs(new_arr - w_array).sum())
            equity *= 1.0 - turnover * cost_rate
            w_array = new_arr
            weights = new_weights
            w_hist.append({"date": dt, **weights})
            conv_hist.append({"date": dt, **conviction})
        else:
            w_hist.append({"date": dt, **weights})
            conv_hist.append({"date": dt, **{t: 0.0 for t in tickers}})

        equity_vals.append(equity)
        ret_vals.append(port_ret)
        pos_vals.append(float(np.sum(w_array)))
        pos_matrix.append(w_array.copy())
        ret_matrix.append(asset_pnl.copy())
        equity_index.append(dt)

    idx = pd.DatetimeIndex(equity_index)
    wh = pd.DataFrame(w_hist).set_index("date") if w_hist else pd.DataFrame()
    ch = pd.DataFrame(conv_hist).set_index("date") if conv_hist else pd.DataFrame()

    return PortfolioSimResult(
        equity=pd.Series(equity_vals, index=idx, name="equity"),
        returns=pd.Series(ret_vals, index=idx, name="returns"),
        positions=pd.Series(pos_vals, index=idx, name="net_exposure"),
        per_ticker_positions=pd.DataFrame(pos_matrix, index=idx, columns=tickers),
        per_ticker_returns=pd.DataFrame(ret_matrix, index=idx, columns=tickers),
        prices=prices,
        label=label,
        meta={
            "initial_capital": initial_capital,
            "cost_bps": cost_bps,
            "warmup": warmup,
            "rebalance_every": rebalance_every,
            "max_position": max_position,
            "gross_exposure": gross_exposure,
            "target_volatility": target_volatility,
            "tickers": tickers,
            "horizons": horizons,
        },
        weights_history=wh,
        conviction_history=ch,
    )
