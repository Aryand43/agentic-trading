"""Run a planned paper experiment and write empirical tables.

Does not change live /api/run. Reuses portfolio backtest, baselines,
walk-forward risk comparison, segments, and the horizon agent.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.agents.horizon_agent import run_horizon_agent
from src.agents.llm import llm_chat
from src.backtest.baselines import run_all_baselines
from src.backtest.metrics import compute_metrics, metrics_to_jsonable, strategy_utility
from src.backtest.portfolio_sim import run_portfolio_backtest
from src.backtest.report import build_report
from src.backtest.trades import write_run_artifacts
from src.config import REPORTS_DIR, RESEARCH
from src.paper.planner import plan_experiment
from src.paper.spec import ExperimentSpec, spec_to_jsonable
from src.risk.engine.data_loader import fetch_benchmark, fetch_research_ohlc
from src.risk.evaluation import evaluate_risk_methods

METRIC_COLS = ("name", "sharpe", "annualized_return", "max_drawdown", "hit_rate", "utility", "n_days")


def _metrics_row(name: str, result) -> dict[str, Any]:
    raw = metrics_to_jsonable(compute_metrics(result.equity, result.returns, result.positions))
    hit = float(raw.get("signal_hit_rate") if raw.get("signal_hit_rate") is not None else raw.get("hit_rate") or 0.0)
    arr = float(raw.get("annualized_return") or 0.0)
    return {
        "name": name,
        "sharpe": raw.get("sharpe"),
        "annualized_return": arr,
        "max_drawdown": raw.get("max_drawdown"),
        "hit_rate": hit,
        "utility": strategy_utility(hit, arr),
        "n_days": raw.get("n_days"),
    }


def _write_table(directory: Path, stem: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / f"{stem}.csv"
    md_path = directory / f"{stem}.md"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if row.get(k) is None else row.get(k) for k in columns})
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [f"# {stem.replace('_', ' ').title()}", "", header, sep]
    for row in rows:
        cells = []
        for k in columns:
            val = row.get(k)
            if val is None:
                cells.append("—")
            elif isinstance(val, float):
                cells.append(f"{val:.4f}" if abs(val) < 10 else f"{val:.4g}")
            elif isinstance(val, bool):
                cells.append("true" if val else "false")
            else:
                cells.append(str(val))
        lines.append("| " + " | ".join(cells) + " |")
    md_path.write_text("\n".join(lines) + "\n")


def _segment_rows(segments: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, block in (segments or {}).items():
        if not isinstance(block, dict):
            continue
        for name, metrics in block.items():
            if name.startswith("_") or not isinstance(metrics, dict):
                continue
            if "sharpe" not in metrics and "n_days" not in metrics:
                continue
            rows.append(
                {
                    "segment": kind,
                    "name": name,
                    "sharpe": metrics.get("sharpe"),
                    "annualized_return": metrics.get("annualized_return"),
                    "max_drawdown": metrics.get("max_drawdown"),
                    "n_days": metrics.get("n_days"),
                    "low_sample": metrics.get("low_sample"),
                }
            )
    return rows


def _methods_blurb(spec: ExperimentSpec, metrics: dict[str, Any], window: dict[str, Any]) -> str | None:
    text = llm_chat(
        "Write one short methods paragraph for a research paper. "
        "Use only the numbers given. Do not invent results. "
        "State this is a historical backtest, not live trading.",
        json.dumps({"spec": spec_to_jsonable(spec), "window": window, "strategy": metrics}, default=str),
        temperature=0.2,
    )
    if not text:
        return None
    return text.strip()


def _readme(
    spec: ExperimentSpec,
    window: dict[str, Any],
    rules: dict[str, Any],
    blurb: str | None,
) -> str:
    lines = [
        "# Paper experiment",
        "",
        "Historical backtest, not live trading.",
        "",
        f"- Window: {window.get('start')} → {window.get('end')} ({window.get('n_days')} trading days)",
        f"- Period: `{spec.period}` · source: `{spec.source}`",
        f"- Tickers: {', '.join(spec.tickers)}",
        f"- Horizons: {', '.join(spec.horizons)}",
        f"- Test days (agent split): {spec.test_days} (RESEARCH default is {RESEARCH['test_days']})",
        f"- Entry: T+1 open (else next close) · TP {rules.get('take_profit_pct')} / SL {rules.get('stop_loss_pct')}",
        f"- Rebalance every {rules.get('rebalance_every')} bars · cost {rules.get('cost_bps')} bps",
        f"- Agent: {'yes ' + ','.join(spec.agent_horizons) + f' × {spec.n_iterations} iters' if spec.include_agent else 'no'}",
        "",
        "Tables are under `tables/`. Trade audit is under `portfolio/`.",
        "",
    ]
    if blurb:
        lines += ["## Methods note", "", blurb, ""]
    return "\n".join(lines)


def run_paper_experiment(
    spec: ExperimentSpec | None = None,
    *,
    plan: bool = False,
    prices: pd.DataFrame | None = None,
    ohlc: dict[str, pd.DataFrame] | None = None,
    benchmark: pd.Series | None = None,
    output_dir: Path | None = None,
    use_cache: bool = True,
    include_industry: bool | None = None,
    use_llm: bool | None = None,
) -> Path:
    """Execute spec (or plan one) and write `reports/paper/<stamp>/`."""
    planned = spec or plan_experiment(force=plan)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(output_dir or (REPORTS_DIR / "paper" / stamp))
    tables = out / "tables"
    out.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    if ohlc is None and prices is None:
        ohlc = fetch_research_ohlc(planned.tickers, period=planned.period, use_cache=use_cache)
    if ohlc is None:
        ohlc = {"Close": prices}
    close = ohlc.get("Close")
    if close is None or close.empty:
        raise ValueError("No Close panel for paper experiment.")
    close = close.sort_index().astype(float)

    if benchmark is None:
        try:
            benchmark = fetch_benchmark(period=planned.period, use_cache=use_cache)
            benchmark = benchmark.reindex(close.index).ffill().dropna()
        except Exception:
            benchmark = None

    portfolio = run_portfolio_backtest(
        close,
        initial_capital=float(RESEARCH["initial_capital"]),
        horizons=list(planned.horizons),
        open_px=ohlc.get("Open"),
        high=ohlc.get("High"),
        low=ohlc.get("Low"),
        write_artifacts=False,
        run_id="portfolio",
    )
    write_run_artifacts(
        "portfolio",
        trades=portfolio.trades,
        config=portfolio.trading_rules or {},
        extra={"window": {
            "start": str(close.index.min())[:10],
            "end": str(close.index.max())[:10],
            "n_days": int(len(close)),
        }},
        directory=out,
    )

    baselines = run_all_baselines(
        close,
        initial_capital=float(RESEARCH["initial_capital"]),
        open_px=ohlc.get("Open"),
        high=ohlc.get("High"),
        low=ohlc.get("Low"),
    )
    strategy_rows = [_metrics_row("multi_horizon_portfolio", portfolio)]
    strategy_rows.extend(_metrics_row(name, br) for name, br in baselines.items())
    _write_table(tables, "strategy_vs_baselines", strategy_rows, list(METRIC_COLS))

    risk_rows = evaluate_risk_methods(portfolio.returns, horizons=list(planned.horizons))
    risk_cols = [
        "method",
        "horizon",
        "confidence",
        "predicted_risk",
        "realized_risk",
        "error",
        "error_metric",
        "breach_rate",
        "n_obs",
        "sample_start",
        "sample_end",
        "low_sample",
        "risk_type",
    ]
    _write_table(tables, "risk_comparison", risk_rows, risk_cols)
    (out / "risk.json").write_text(json.dumps(risk_rows, indent=2, default=str))

    industry = include_industry if include_industry is not None else len(list(close.columns)) <= 10
    report = build_report(
        portfolio,
        benchmark=benchmark,
        baseline_results=baselines,
        include_industry=industry,
        title="paper_portfolio",
    )
    seg_rows = _segment_rows(report.get("segments") or {})
    _write_table(
        tables,
        "segments",
        seg_rows,
        ["segment", "name", "sharpe", "annualized_return", "max_drawdown", "n_days", "low_sample"],
    )

    agent_rows: list[dict[str, Any]] = []
    agent_dirs: list[str] = []
    if planned.include_agent:
        llm_flag = bool(use_llm) if use_llm is not None else True
        for horizon in planned.agent_horizons:
            summary = run_horizon_agent(
                close,
                horizon=horizon,
                n_iterations=planned.n_iterations,
                test_days=planned.test_days,
                initial_capital=float(RESEARCH["initial_capital"]),
                benchmark=benchmark,
                use_llm=llm_flag,
                output_dir=out / "agent" / horizon,
                seed_baselines=True,
            )
            agent_dirs.append(summary.run_dir)
            for row in summary.leaderboard:
                agent_rows.append(
                    {
                        "horizon": horizon,
                        "iteration": row.get("iteration"),
                        "name": row.get("name"),
                        "template": row.get("template"),
                        "test_utility": row.get("test_utility"),
                        "test_sharpe": row.get("test_sharpe"),
                        "test_hit": row.get("test_hit"),
                        "code_hash": row.get("code_hash"),
                    }
                )
        if agent_rows:
            _write_table(
                tables,
                "agent_leaderboard",
                agent_rows,
                [
                    "horizon",
                    "iteration",
                    "name",
                    "template",
                    "test_utility",
                    "test_sharpe",
                    "test_hit",
                    "code_hash",
                ],
            )

    window = {
        "start": close.index.min().strftime("%Y-%m-%d")
        if hasattr(close.index.min(), "strftime")
        else str(close.index.min())[:10],
        "end": close.index.max().strftime("%Y-%m-%d")
        if hasattr(close.index.max(), "strftime")
        else str(close.index.max())[:10],
        "n_days": int(len(close)),
        "period": planned.period,
    }
    spec_payload = {
        "planned": spec_to_jsonable(planned),
        "executed": spec_to_jsonable(planned),
        "source": planned.source,
        "window": window,
        "trading_rules": portfolio.trading_rules,
        "note": (
            f"test_days={planned.test_days} overrides RESEARCH test_days="
            f"{RESEARCH['test_days']} so empirical tables have a usable holdout."
        ),
        "agent_run_dirs": agent_dirs,
        "artifact_dir": str(out),
    }
    (out / "spec.json").write_text(json.dumps(spec_payload, indent=2, default=str))

    blurb = _methods_blurb(planned, strategy_rows[0], window)
    (out / "README.md").write_text(_readme(planned, window, portfolio.trading_rules or {}, blurb))
    return out
