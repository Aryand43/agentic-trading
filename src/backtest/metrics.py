"""Performance metrics used in backtest tearsheets."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from src.config import TRADING_DAYS_PER_YEAR


def max_drawdown(equity: pd.Series) -> float:
    """Maximum peak-to-trough drawdown as a negative fraction (e.g. -0.22)."""
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min()) if len(dd) else 0.0


def sharpe_ratio(returns: pd.Series, risk_free: float = 0.0) -> float:
    """Annualized Sharpe from daily simple returns."""
    clean = returns.dropna()
    if len(clean) < 2:
        return 0.0
    excess = clean - risk_free / TRADING_DAYS_PER_YEAR
    vol = excess.std()
    if vol == 0 or math.isnan(vol):
        return 0.0
    return float(np.sqrt(TRADING_DAYS_PER_YEAR) * excess.mean() / vol)


def day_hit_rate(returns: pd.Series, positions: pd.Series | None = None) -> float:
    """Fraction of periods with positive PnL when a position is held (legacy)."""
    ret = returns.dropna()
    if positions is not None:
        pos = positions.reindex(ret.index).fillna(0.0)
        mask = pos.abs() > 1e-12
        ret = ret[mask]
    else:
        ret = ret[ret != 0]
    if ret.empty:
        return 0.0
    return float((ret > 0).mean())


def hit_rate(returns: pd.Series, positions: pd.Series | None = None) -> float:
    """Legacy alias: day PnL hit rate. Prefer ``signal_hit_rate`` for Rui semantics."""
    return day_hit_rate(returns, positions)


def signal_hit_rate(
    signals: pd.Series,
    forward_returns: pd.Series,
    *,
    flat_threshold: float = 0.05,
) -> float:
    """Accuracy of non-flat buy/sell signals (Rui hit-rate definition).

    Flat signals (|signal| < flat_threshold) are excluded because they do not
    force a trade. Buy (signal > thr) is correct when forward_return > 0;
    sell (signal < -thr) is correct when forward_return < 0.
    """
    sig = signals.astype(float)
    fwd = forward_returns.astype(float)
    aligned = pd.concat([sig, fwd], axis=1, join="inner").dropna()
    if aligned.empty:
        return 0.0
    s = aligned.iloc[:, 0]
    r = aligned.iloc[:, 1]
    active = s.abs() >= float(flat_threshold)
    if not active.any():
        return 0.0
    s_a = s[active]
    r_a = r[active]
    buy = s_a > 0
    sell = s_a < 0
    correct = (buy & (r_a > 0)) | (sell & (r_a < 0))
    return float(correct.mean())


def strategy_utility(
    signal_hit: float,
    annualized_return: float,
    *,
    w_hit: float | None = None,
    w_arr: float | None = None,
) -> float:
    """Scalar fitness combining signal hit rate and ARR (Rui utility curve)."""
    from src.config import RESEARCH

    w_hit = float(w_hit if w_hit is not None else RESEARCH.get("utility_w_hit", 0.5))
    w_arr = float(w_arr if w_arr is not None else RESEARCH.get("utility_w_arr", 0.5))
    # Map ARR into roughly [-1, 1] so it is combinable with hit ∈ [0, 1]
    arr_term = float(np.tanh(float(annualized_return or 0.0)))
    # Center hit around 0.5 → [-0.5, 0.5] then shift utility to [0, ~1]
    hit_term = float(signal_hit or 0.0)
    return float(w_hit * hit_term + w_arr * (0.5 + 0.5 * arr_term))


def total_return(equity: pd.Series) -> float:
    if equity.empty or equity.iloc[0] == 0:
        return 0.0
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def annualized_return(equity: pd.Series) -> float:
    if equity.empty or len(equity) < 2 or equity.iloc[0] <= 0:
        return 0.0
    years = len(equity) / TRADING_DAYS_PER_YEAR
    if years <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)


def turnover_series(positions: pd.Series) -> float:
    """Mean absolute daily change in position (gross turnover rate)."""
    if positions is None or len(positions) < 2:
        return 0.0
    return float(positions.diff().abs().dropna().mean())


def compute_metrics(
    equity: pd.Series,
    returns: pd.Series | None = None,
    positions: pd.Series | None = None,
) -> dict[str, float]:
    """Standard tearsheet metrics for an equity curve."""
    equity = equity.dropna()
    if returns is None:
        returns = equity.pct_change().fillna(0.0)
    else:
        returns = returns.reindex(equity.index).fillna(0.0)

    day_hit = day_hit_rate(returns, positions)
    arr = annualized_return(equity)
    out = {
        "total_return": total_return(equity),
        "annualized_return": arr,
        "sharpe": sharpe_ratio(returns),
        "max_drawdown": max_drawdown(equity),
        "hit_rate": day_hit,  # legacy PnL hit (kept for API compat)
        "day_hit_rate": day_hit,
        "turnover": turnover_series(positions) if positions is not None else 0.0,
        "n_days": float(len(equity)),
        "final_equity": float(equity.iloc[-1]) if len(equity) else 0.0,
        "start_equity": float(equity.iloc[0]) if len(equity) else 0.0,
    }
    return out


def metrics_to_jsonable(metrics: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in metrics.items():
        if isinstance(v, (float, np.floating)):
            out[k] = None if (math.isnan(float(v)) or math.isinf(float(v))) else float(v)
        elif isinstance(v, (int, np.integer)):
            out[k] = int(v)
        else:
            out[k] = v
    return out
