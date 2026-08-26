"""Point-in-time single-name and multi-name signal backtester (daily bars).

Walks history day-by-day, scores each ticker with only past prices (no lookahead),
maps score → signed position, applies simple transaction costs, accumulates PnL.

Execution details (T+1 open, TP/SL, horizon exit, trade audit) live in
``src.backtest.execution``. This module keeps the public ``BacktestResult``
and ``run_signal_backtest`` entry points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Callable

import pandas as pd

from src.backtest.trades import SignalEvent, TradeRecord
from src.backtest.trading_rules import TradingRules, default_trading_rules
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
    trades: list[TradeRecord] = field(default_factory=list)
    signal_events: list[SignalEvent] = field(default_factory=list)
    trading_rules: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""
    artifact_paths: dict[str, str] = field(default_factory=dict)
    weights_history: pd.DataFrame = field(default_factory=pd.DataFrame)


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
    open_px: Optional[pd.DataFrame] = None,
    high: Optional[pd.DataFrame] = None,
    low: Optional[pd.DataFrame] = None,
    trading_rules: Optional[TradingRules] = None,
    write_artifacts: bool = False,
    run_id: Optional[str] = None,
    take_profit_pct: Optional[float] = None,
    stop_loss_pct: Optional[float] = None,
    side_mode: Optional[str] = None,
    slippage_bps: Optional[float] = None,
) -> BacktestResult:
    """Backtest a signal function over a multi-ticker Close panel.

    Signals at T use prices through T only. Entries fill at T+1 open when
    ``open_px`` is provided, otherwise at T+1 close (never fabricated).
    """
    if prices is None or prices.empty:
        raise ValueError("prices panel is empty")

    prices = prices.sort_index().astype(float)
    signal_fn = signal_fn or _default_signal_fn(horizon)
    overrides: dict[str, Any] = {
        "horizons": [horizon],
        "initial_capital": (
            float(initial_capital)
            if initial_capital is not None
            else RESEARCH["initial_capital"]
        ),
        "cost_bps": float(cost_bps if cost_bps is not None else RESEARCH["cost_bps"]),
        "warmup_bars": int(warmup if warmup is not None else RESEARCH["warmup_bars"]),
        "rebalance_every": int(rebalance_every),
    }
    if take_profit_pct is not None:
        overrides["take_profit_pct"] = take_profit_pct
    if stop_loss_pct is not None:
        overrides["stop_loss_pct"] = stop_loss_pct
    if side_mode is not None:
        overrides["side_mode"] = side_mode
    if slippage_bps is not None:
        overrides["slippage_bps"] = slippage_bps

    rules = trading_rules or default_trading_rules(**overrides)
    if trading_rules is not None:
        rules = trading_rules.model_copy(
            update={
                k: v
                for k, v in overrides.items()
                if k
                in {
                    "horizons",
                    "initial_capital",
                    "cost_bps",
                    "warmup_bars",
                    "rebalance_every",
                }
            }
        )

    from src.backtest.execution import result_from_execution, simulate

    ex = simulate(
        prices,
        rules=rules,
        signal_fn=signal_fn,
        horizon=horizon,
        open_px=open_px,
        high=high,
        low=low,
        use_multi_horizon=False,
        run_id=run_id,
        label=label or horizon,
        write_artifacts=write_artifacts,
    )
    return result_from_execution(ex, prices, label=label or horizon)
