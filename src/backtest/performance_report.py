"""Aradia / Rui-style strategy performance reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult
from src.backtest.metrics import compute_metrics, metrics_to_jsonable, strategy_utility
from src.backtest.portfolios import evaluate_portfolios, top_stocks_by_utility
from src.backtest.report import build_report, write_report
from src.backtest.splits import SplitWindows
from src.config import RESEARCH


TEMPLATE_META: dict[str, dict[str, str]] = {
    "sma_rsi": {
        "family": "SMA Cross + RSI",
        "principle": "Trend-follow with SMA cross; RSI blends confirmation / fade extremes.",
        "equation": "s = 0.6*tanh((SMA_f - SMA_s)/(0.02*SMA_s)) + 0.4*(RSI-50)/50",
        "trading_rules": (
            "Equal-weight panel; score ∈ [-1,1] maps to long/short weight. "
            "Rebalance daily after warm-up. Flat when |score| near 0."
        ),
    },
    "bollinger_squeeze": {
        "family": "Bollinger squeeze breakout",
        "principle": "Volatility squeeze expansion in direction of price vs mid band.",
        "equation": "s = squeeze_intensity * sign(close - mid)",
        "trading_rules": "Long above mid on squeeze release; short below; scale by intensity.",
    },
    "reversal": {
        "family": "Short-term reversal",
        "principle": "Fades extreme multi-day returns vs rolling z-score window.",
        "equation": "s = clip(-z/2) on lookback return z-score",
        "trading_rules": "Mean-revert after stretched moves; hold until next rebalance.",
    },
    "momentum_skip": {
        "family": "Momentum with skip",
        "principle": "Classic formation-period momentum skipping the most recent month.",
        "equation": "s = clip(z/2) of form-period return ending skip bars before last close",
        "trading_rules": "Long high-momentum names, short low-momentum after skip window.",
    },
    "buy_and_hold": {
        "family": "Baseline buy & hold",
        "principle": "Always fully long the universe.",
        "equation": "s = 1",
        "trading_rules": "Always long every name; no discretionary exit.",
    },
    "sma_cross": {
        "family": "SMA crossover baseline",
        "principle": "Binary trend: long when fast SMA > slow SMA.",
        "equation": "s = +1 if SMA_f > SMA_s else -1",
        "trading_rules": "Flip long/short on crossover; equal weight.",
    },
    "rsi_mean_reversion": {
        "family": "RSI mean reversion baseline",
        "principle": "Long oversold RSI, short overbought.",
        "equation": "s based on RSI(period) vs 30/70 bands",
        "trading_rules": "Enter on RSI extremes; soft fade mid-band.",
    },
    "momentum_20d": {
        "family": "20d momentum baseline",
        "principle": "Sign of trailing 20-day return.",
        "equation": "s = clip(r_20 / 0.1)",
        "trading_rules": "Long recent winners, short recent losers.",
    },
}


def _risk_mirrors(prices: pd.DataFrame) -> dict[str, Any]:
    """Lightweight stock vol (std) + proxy portfolio VaR on daily returns."""
    rets = prices.pct_change().dropna(how="all")
    if rets.empty:
        return {}
    stock_vols = rets.std() * np.sqrt(252)
    equal_w = np.ones(len(rets.columns)) / max(len(rets.columns), 1)
    port = rets.fillna(0.0).values @ equal_w
    # Historical 95% VaR (positive number loss)
    var95 = float(-np.percentile(port, 5)) if len(port) else 0.0
    return {
        "median_stock_vol_ann": float(stock_vols.median()) if len(stock_vols) else 0.0,
        "mean_stock_vol_ann": float(stock_vols.mean()) if len(stock_vols) else 0.0,
        "portfolio_hist_var_95_daily": var95,
        "portfolio_hist_var_95_ann": var95 * np.sqrt(252),
    }


def build_strategy_performance_report(
    *,
    name: str,
    template: str,
    params: dict[str, float],
    principle: str | None,
    signal_fn,
    splits: SplitWindows,
    train_result: BacktestResult | None = None,
    full_result: BacktestResult | None = None,
    benchmark: pd.Series | None = None,
    initial_capital: float | None = None,
    cost_bps: float | None = None,
    warmup: int | None = None,
) -> dict[str, Any]:
    """Full Rui/Aradia-style performance package for one strategy."""
    initial_capital = float(
        initial_capital if initial_capital is not None else RESEARCH["initial_capital"]
    )
    cost_bps = float(cost_bps if cost_bps is not None else RESEARCH["cost_bps"])
    warmup = int(warmup if warmup is not None else RESEARCH["warmup_bars"])
    meta = TEMPLATE_META.get(template, {})
    principle = principle or meta.get("principle") or f"Template {template}"

    port_eval = evaluate_portfolios(
        splits.train,
        splits.val,
        splits.test,
        signal_fn,
        warmup=warmup,
        initial_capital=initial_capital,
        cost_bps=cost_bps,
    )

    segment_report: dict[str, Any] = {}
    if full_result is not None:
        segment_report = build_report(
            full_result,
            benchmark=benchmark,
            include_industry=len(splits.train.columns) <= 12,
            title=name,
        )

    p1_test = (port_eval.get("portfolios") or {}).get("P1", {}).get("test") or {}
    test_utility = float(p1_test.get("utility") or 0.0)
    test_hit = float(p1_test.get("signal_hit_rate") or p1_test.get("hit_rate") or 0.0)
    test_arr = float(p1_test.get("annualized_return") or 0.0)

    overall = {}
    if train_result is not None:
        overall = metrics_to_jsonable(
            compute_metrics(
                train_result.equity, train_result.returns, train_result.positions
            )
        )
        overall["utility"] = strategy_utility(
            float(overall.get("hit_rate") or 0),
            float(overall.get("annualized_return") or 0),
        )

    report: dict[str, Any] = {
        "title": name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": {
            "name": name,
            "family": meta.get("family") or template,
            "template": template,
            "params": params,
            "principle": principle,
            "equation": meta.get("equation") or "",
            "trading_rules": meta.get("trading_rules") or "",
        },
        "windows": splits.to_dict(),
        "overall": overall,
        "portfolios": port_eval.get("portfolios") or {},
        "per_stock_favorites": top_stocks_by_utility(
            port_eval.get("train_stock_stats") or {}, k=8
        ),
        "segments": (segment_report.get("segments") if segment_report else {}),
        "risk": _risk_mirrors(pd.concat([splits.train, splits.val, splits.test])),
        "test_summary": {
            "utility": test_utility,
            "signal_hit_rate": test_hit,
            "annualized_return": test_arr,
            "sharpe": float(p1_test.get("sharpe") or 0.0),
            "max_drawdown": float(p1_test.get("max_drawdown") or 0.0),
        },
        "equity_curve": (segment_report.get("equity_curve") if segment_report else []),
    }
    return report


def performance_to_markdown(report: dict[str, Any]) -> str:
    s = report.get("strategy") or {}
    w = report.get("windows") or {}
    lines = [
        f"# {report.get('title', 'Strategy Performance')}",
        "",
        f"Generated: `{report.get('generated_at', '')}`",
        "",
        "## Strategy summary",
        "",
        f"- **Name**: {s.get('name')}",
        f"- **Family**: {s.get('family')}",
        f"- **Parameters**: `{json.dumps(s.get('params') or {})}`",
        f"- **Principle**: {s.get('principle')}",
        f"- **Equation**: `{s.get('equation')}`",
        f"- **Trading rules**: {s.get('trading_rules')}",
        "",
        "## Windows (train / val / test)",
        "",
        f"| Split | Start | End | Days |",
        f"|---|---|---|---:|",
    ]
    for key in ("train", "val", "test"):
        b = w.get(key) or {}
        lines.append(
            f"| {key} | {b.get('start')} | {b.get('end')} | {b.get('n_days')} |"
        )
    lines += ["", "## Portfolio results (Rui P1–P4)", ""]

    ports = report.get("portfolios") or {}
    for pname, block in ports.items():
        lines.append(f"### {pname} ({block.get('n_stocks', 0)} stocks)")
        lines.append("")
        lines.append(
            "| Split | n stocks | Signal hit | ARR | Sharpe | Max DD | Utility |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for split in ("train", "val", "test"):
            m = block.get(split) or {}
            lines.append(
                f"| {split} | {m.get('n_stocks', 0)} | "
                f"{m.get('signal_hit_rate', m.get('hit_rate', 0)):.2%} | "
                f"{m.get('annualized_return', 0):.2%} | "
                f"{m.get('sharpe', 0):.3f} | "
                f"{m.get('max_drawdown', 0):.2%} | "
                f"{m.get('utility', 0):.3f} |"
            )
        lines.append("")

    ts = report.get("test_summary") or {}
    lines += [
        "## Test summary (P1)",
        "",
        f"- Utility: **{ts.get('utility', 0):.3f}**",
        f"- Signal hit: {ts.get('signal_hit_rate', 0):.2%}",
        f"- ARR: {ts.get('annualized_return', 0):.2%}",
        f"- Sharpe: {ts.get('sharpe', 0):.3f}",
        f"- Max DD: {ts.get('max_drawdown', 0):.2%}",
        "",
    ]

    risk = report.get("risk") or {}
    if risk:
        lines += [
            "## Risk mirrors",
            "",
            f"- Median stock vol (ann): {risk.get('median_stock_vol_ann', 0):.2%}",
            f"- Portfolio hist VaR 95% (daily): {risk.get('portfolio_hist_var_95_daily', 0):.4f}",
            "",
        ]

    fav = report.get("per_stock_favorites") or []
    if fav:
        lines += ["## Per-stock favorites (train utility)", ""]
        for row in fav:
            lines.append(
                f"- **{row.get('ticker')}**: util={row.get('utility', 0):.3f}, "
                f"hit={row.get('signal_hit_rate', 0):.2%}, "
                f"ARR={row.get('annualized_return', 0):.2%}"
            )
        lines.append("")

    return "\n".join(lines)


def write_performance_report(
    report: dict[str, Any],
    directory: Path,
    *,
    stem: str = "performance",
) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{stem}.json"
    md_path = directory / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str))
    md_path.write_text(performance_to_markdown(report))
    # also publish via standard report writer for latest_* convenience
    try:
        write_report(report, name=stem, directory=directory)
    except Exception:
        pass
    return json_path
