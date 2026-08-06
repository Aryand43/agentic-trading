"""Classic technical-analysis style baselines under the same backtest harness.

These deliberately avoid a binary TA library dependency (fragile on some platforms)
while matching the spirit of common TA package strategies Rui referenced as baselines.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult, SignalFn, run_signal_backtest
from src.signals.strategies import _rsi


def signal_buy_and_hold(prices: pd.Series) -> float:
    """Always fully long."""
    return 1.0 if len(prices) >= 2 else 0.0


def signal_sma_cross(prices: pd.Series, fast: int = 10, slow: int = 50) -> float:
    """+1 when SMA(fast) > SMA(slow), else -1 (classic TA trend)."""
    if len(prices) < slow:
        return 0.0
    sma_f = prices.rolling(fast).mean().iloc[-1]
    sma_s = prices.rolling(slow).mean().iloc[-1]
    if np.isnan(sma_f) or np.isnan(sma_s):
        return 0.0
    return 1.0 if sma_f > sma_s else -1.0


def signal_rsi_mean_reversion(
    prices: pd.Series, period: int = 14, low: float = 30.0, high: float = 70.0
) -> float:
    """Long when RSI oversold, short when overbought, flat in between."""
    if len(prices) < period + 2:
        return 0.0
    val = float(_rsi(prices, period).iloc[-1])
    if np.isnan(val):
        return 0.0
    if val < low:
        return 1.0
    if val > high:
        return -1.0
    # Soft fade toward extremes
    if val < 50:
        return float((50 - val) / 20.0) * 0.5
    return float(-(val - 50) / 20.0) * 0.5


def signal_momentum_20d(prices: pd.Series, lookback: int = 20) -> float:
    """Sign of trailing N-day return (simple price momentum)."""
    if len(prices) < lookback + 1:
        return 0.0
    ret = prices.iloc[-1] / prices.iloc[-lookback - 1] - 1.0
    return float(np.clip(ret / 0.1, -1.0, 1.0))


BASELINE_SIGNAL_FNS: dict[str, SignalFn] = {
    "buy_and_hold": signal_buy_and_hold,
    "sma_cross": signal_sma_cross,
    "rsi_mean_reversion": signal_rsi_mean_reversion,
    "momentum_20d": signal_momentum_20d,
}


def run_baseline(
    prices: pd.DataFrame,
    name: str,
    **kwargs,
) -> BacktestResult:
    """Run a named classic TA baseline on the same panel as strategy backtests."""
    if name not in BASELINE_SIGNAL_FNS:
        raise ValueError(f"Unknown baseline {name!r}. Choose from {list(BASELINE_SIGNAL_FNS)}")
    return run_signal_backtest(
        prices,
        signal_fn=BASELINE_SIGNAL_FNS[name],
        label=name,
        **kwargs,
    )


def run_all_baselines(prices: pd.DataFrame, **kwargs) -> dict[str, BacktestResult]:
    return {name: run_baseline(prices, name, **kwargs) for name in BASELINE_SIGNAL_FNS}
