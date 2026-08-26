"""Historical multi-horizon portfolio rebalance simulation.

Uses the live construction path (blend horizons → inv-vol weights → target vol)
on rolling daily history to produce an equity curve from initial capital
(default $10k over multi-year daily bars).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.backtest.engine import BacktestResult
from src.backtest.execution import result_from_execution, simulate
from src.backtest.trading_rules import TradingRules, default_trading_rules
from src.config import HORIZONS, RESEARCH


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
    open_px: pd.DataFrame | None = None,
    high: pd.DataFrame | None = None,
    low: pd.DataFrame | None = None,
    trading_rules: TradingRules | None = None,
    write_artifacts: bool = False,
    run_id: str | None = None,
    take_profit_pct: float | None = None,
    stop_loss_pct: float | None = None,
    side_mode: str | None = None,
    slippage_bps: float | None = None,
) -> PortfolioSimResult:
    """Rebalance a multi-horizon risk-aware portfolio over daily history."""
    prices = prices.sort_index().astype(float)
    horizons = horizons or list(HORIZONS)
    overrides = {
        "horizons": list(horizons),
        "initial_capital": float(
            initial_capital if initial_capital is not None else RESEARCH["initial_capital"]
        ),
        "cost_bps": float(cost_bps if cost_bps is not None else RESEARCH["cost_bps"]),
        "warmup_bars": int(warmup if warmup is not None else RESEARCH["warmup_bars"]),
        "rebalance_every": int(
            rebalance_every if rebalance_every is not None else RESEARCH["rebalance_every"]
        ),
        "max_position": float(max_position),
        "gross_exposure": float(gross_exposure),
        "target_volatility": float(target_volatility),
        "max_leverage": float(max_leverage),
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
        rules = trading_rules.model_copy(update=overrides)

    ex = simulate(
        prices,
        rules=rules,
        use_multi_horizon=True,
        open_px=open_px,
        high=high,
        low=low,
        run_id=run_id,
        label=label,
        write_artifacts=write_artifacts,
    )
    base = result_from_execution(ex, prices, label=label)
    return PortfolioSimResult(
        equity=base.equity,
        returns=base.returns,
        positions=base.positions,
        per_ticker_positions=base.per_ticker_positions,
        per_ticker_returns=base.per_ticker_returns,
        prices=prices,
        label=label,
        meta=base.meta,
        trades=base.trades,
        signal_events=base.signal_events,
        trading_rules=base.trading_rules,
        run_id=base.run_id,
        artifact_paths=base.artifact_paths,
        weights_history=ex.weights_history,
        conviction_history=ex.conviction_history,
    )
