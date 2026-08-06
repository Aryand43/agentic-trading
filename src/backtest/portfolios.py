"""Multi-portfolio evaluation (Rui P1–P4) on train-selected universes."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult, SignalFn, run_signal_backtest
from src.backtest.metrics import (
    annualized_return,
    compute_metrics,
    metrics_to_jsonable,
    signal_hit_rate,
    strategy_utility,
)
from src.config import RESEARCH

# Portfolio label → (hit_percentile, arr_percentile); None = all stocks
PORTFOLIO_SPECS: dict[str, tuple[float | None, float | None]] = {
    "P1": (None, None),  # all stocks
    "P2": (0.50, 0.50),  # top 50% hit ∩ top 50% ARR
    "P3": (0.30, 0.30),
    "P4": (0.10, 0.10),
}


def _per_ticker_stats(
    prices: pd.DataFrame,
    signal_fn: SignalFn,
    *,
    warmup: int,
    flat_threshold: float = 0.05,
) -> dict[str, dict[str, float]]:
    """Per-name signal hit rate and ARR over the price window (train)."""
    stats: dict[str, dict[str, float]] = {}
    for t in prices.columns:
        series = prices[t].dropna()
        if len(series) < warmup + 10:
            continue
        signals = []
        dates = []
        for i in range(warmup, len(series)):
            try:
                s = float(np.clip(signal_fn(series.iloc[: i + 1]), -1.0, 1.0))
            except Exception:
                s = 0.0
            signals.append(s)
            dates.append(series.index[i])
        if not signals:
            continue
        sig = pd.Series(signals, index=pd.DatetimeIndex(dates))
        # next-day return aligned to signal day (decision at close, realize next)
        fwd = series.pct_change().shift(-1).reindex(sig.index)
        hit = signal_hit_rate(sig, fwd, flat_threshold=flat_threshold)
        # simple long-on-buy equity for ARR
        pos = (sig > flat_threshold).astype(float) - (sig < -flat_threshold).astype(float)
        day_r = series.pct_change().reindex(sig.index).fillna(0.0)
        pnl = (pos.shift(1).fillna(0.0) * day_r).fillna(0.0)
        eq = (1.0 + pnl).cumprod() * float(RESEARCH["initial_capital"])
        arr = annualized_return(eq)
        stats[t] = {
            "signal_hit_rate": hit,
            "annualized_return": arr,
            "n_signals": float((sig.abs() >= flat_threshold).sum()),
        }
    return stats


def select_portfolio(
    train_stats: dict[str, dict[str, float]],
    *,
    hit_pct: float | None,
    arr_pct: float | None,
) -> list[str]:
    """Intersection of top hit and top ARR percentiles; fall back to all if empty."""
    tickers = list(train_stats.keys())
    if not tickers:
        return []
    if hit_pct is None and arr_pct is None:
        return tickers

    hit_s = pd.Series({t: train_stats[t]["signal_hit_rate"] for t in tickers})
    arr_s = pd.Series({t: train_stats[t]["annualized_return"] for t in tickers})

    def top_set(s: pd.Series, pct: float) -> set[str]:
        if len(s) == 1:
            return set(s.index)
        # top fraction: e.g. 0.50 → names at or above median
        thr = s.quantile(1.0 - pct)
        picked = set(s[s >= thr].index)
        if not picked:
            # take top 1
            picked = {s.idxmax()}
        return picked

    if hit_pct is None:
        return list(top_set(arr_s, arr_pct or 0.5))
    if arr_pct is None:
        return list(top_set(hit_s, hit_pct or 0.5))
    inter = top_set(hit_s, hit_pct) & top_set(arr_s, arr_pct)
    if not inter:
        # union of tops if intersection empty on tiny panels
        inter = top_set(hit_s, hit_pct) | top_set(arr_s, arr_pct)
    return sorted(inter)


def _panel_metrics(
    prices: pd.DataFrame,
    signal_fn: SignalFn,
    tickers: list[str],
    *,
    warmup: int,
    initial_capital: float,
    cost_bps: float,
    flat_threshold: float = 0.05,
) -> dict[str, Any]:
    if not tickers:
        empty = metrics_to_jsonable(
            compute_metrics(pd.Series([initial_capital], dtype=float))
        )
        empty["n_stocks"] = 0
        empty["signal_hit_rate"] = 0.0
        empty["utility"] = 0.0
        return empty

    subset = prices[tickers].dropna(how="all")
    if subset.empty or len(subset) <= warmup + 2:
        empty = metrics_to_jsonable(
            compute_metrics(pd.Series([initial_capital], dtype=float))
        )
        empty["n_stocks"] = len(tickers)
        empty["signal_hit_rate"] = 0.0
        empty["utility"] = 0.0
        return empty

    res = run_signal_backtest(
        subset,
        signal_fn=signal_fn,
        initial_capital=initial_capital,
        cost_bps=cost_bps,
        warmup=min(warmup, max(20, len(subset) // 3)),
        label="portfolio_slice",
    )
    m = metrics_to_jsonable(
        compute_metrics(res.equity, res.returns, res.positions)
    )
    # Aggregate signal hit from per-ticker positions (pos = score/N)
    n = max(len(tickers), 1)
    hits = []
    for t in tickers:
        if t not in res.per_ticker_positions.columns:
            continue
        pos = res.per_ticker_positions[t]
        sig = pos * n
        if t not in subset.columns:
            continue
        px = subset[t]
        fwd = px.pct_change().shift(-1).reindex(sig.index)
        hits.append(signal_hit_rate(sig, fwd, flat_threshold=flat_threshold))
    sig_hit = float(np.mean(hits)) if hits else float(m.get("hit_rate") or 0.0)
    m["signal_hit_rate"] = sig_hit
    m["n_stocks"] = len(tickers)
    m["n_stocks_traded"] = int(
        (res.per_ticker_positions.abs().sum(axis=0) > 1e-9).sum()
    ) if not res.per_ticker_positions.empty else 0
    m["utility"] = strategy_utility(sig_hit, float(m.get("annualized_return") or 0.0))
    # Primary hit_rate in Rui reports = signal hit
    m["hit_rate"] = sig_hit
    return m


def evaluate_portfolios(
    train_px: pd.DataFrame,
    val_px: pd.DataFrame,
    test_px: pd.DataFrame,
    signal_fn: SignalFn,
    *,
    warmup: int | None = None,
    initial_capital: float | None = None,
    cost_bps: float | None = None,
) -> dict[str, Any]:
    """Select P1–P4 on train; report metrics on train/val/test."""
    warmup = int(warmup if warmup is not None else RESEARCH["warmup_bars"])
    initial_capital = float(
        initial_capital if initial_capital is not None else RESEARCH["initial_capital"]
    )
    cost_bps = float(cost_bps if cost_bps is not None else RESEARCH["cost_bps"])
    # Use shorter warmup on short slices
    warm_train = min(warmup, max(30, len(train_px) // 4))

    train_stats = _per_ticker_stats(train_px, signal_fn, warmup=warm_train)
    out: dict[str, Any] = {"train_stock_stats": train_stats, "portfolios": {}}

    for name, (hit_p, arr_p) in PORTFOLIO_SPECS.items():
        selected = select_portfolio(train_stats, hit_pct=hit_p, arr_pct=arr_p)
        if not selected and len(train_px.columns):
            selected = list(train_px.columns)
        block = {
            "tickers": selected,
            "n_stocks": len(selected),
            "train": _panel_metrics(
                train_px, signal_fn, selected,
                warmup=warm_train,
                initial_capital=initial_capital,
                cost_bps=cost_bps,
            ),
            "val": _panel_metrics(
                val_px, signal_fn, [t for t in selected if t in val_px.columns],
                warmup=min(warm_train, max(15, len(val_px) // 4)),
                initial_capital=initial_capital,
                cost_bps=cost_bps,
            ),
            "test": _panel_metrics(
                test_px, signal_fn, [t for t in selected if t in test_px.columns],
                warmup=min(warm_train, max(10, len(test_px) // 4)),
                initial_capital=initial_capital,
                cost_bps=cost_bps,
            ),
        }
        out["portfolios"][name] = block
    return out


def top_stocks_by_utility(train_stats: dict[str, dict[str, float]], k: int = 5) -> list[dict]:
    """Per-stock favorites ranked by train utility (for report)."""
    rows = []
    for t, s in train_stats.items():
        u = strategy_utility(s["signal_hit_rate"], s["annualized_return"])
        rows.append(
            {
                "ticker": t,
                "signal_hit_rate": s["signal_hit_rate"],
                "annualized_return": s["annualized_return"],
                "utility": u,
                "n_signals": s.get("n_signals", 0),
            }
        )
    rows.sort(key=lambda r: r["utility"], reverse=True)
    return rows[:k]
