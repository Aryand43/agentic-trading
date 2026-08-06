"""CLI: multi-year daily backtests, baselines, portfolio equity curve, and reports.

Run from repo root:
    python -m examples.run_backtest
    python -m examples.run_backtest --horizon 10d --tickers AAPL,MSFT,NVDA
    python -m examples.run_backtest --portfolio --agent --agent-iters 2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root on path when run as script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.horizon_agent import risk_agent_experiment, run_horizon_agent
from src.backtest.baselines import run_all_baselines
from src.backtest.engine import run_signal_backtest
from src.backtest.metrics import compute_metrics, metrics_to_jsonable
from src.backtest.portfolio_sim import run_portfolio_backtest
from src.backtest.report import build_report, write_report
from src.config import RESEARCH, REPORTS_DIR
from src.risk.engine.data_loader import fetch_benchmark, fetch_research_prices
from src.signals.strategies import get_signal


def main() -> None:
    parser = argparse.ArgumentParser(description="Research backtest + report CLI")
    parser.add_argument(
        "--tickers",
        type=str,
        default=",".join(RESEARCH["tickers"][:6]),
        help="Comma-separated tickers",
    )
    parser.add_argument("--horizon", type=str, default="10d")
    parser.add_argument("--period", type=str, default=RESEARCH["period"])
    parser.add_argument("--capital", type=float, default=RESEARCH["initial_capital"])
    parser.add_argument("--portfolio", action="store_true", help="Run multi-horizon portfolio sim")
    parser.add_argument("--agent", action="store_true", help="Run horizon discovery agent")
    parser.add_argument("--agent-iters", type=int, default=2)
    parser.add_argument("--risk-agent", action="store_true", help="Rank risk target-vol variants")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--no-industry", action="store_true", help="Skip sector lookup (faster)")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    print(f"Fetching research prices for {tickers} ({args.period} daily)...")
    prices = fetch_research_prices(tickers, period=args.period, use_cache=not args.no_cache)
    print(f"  panel shape={prices.shape}, {prices.index.min().date()} → {prices.index.max().date()}")

    print(f"Fetching benchmark {RESEARCH['benchmark']}...")
    try:
        benchmark = fetch_benchmark(period=args.period, use_cache=not args.no_cache)
    except Exception as exc:
        print(f"  benchmark unavailable ({exc}); regime segments will be empty")
        benchmark = None

    # Horizon strategy backtest
    print(f"\n=== Horizon strategy: {args.horizon} ===")
    strat = run_signal_backtest(
        prices,
        signal_fn=lambda p: get_signal("", args.horizon, p),
        horizon=args.horizon,
        initial_capital=args.capital,
        label=f"strategy_{args.horizon}",
    )
    strat_metrics = metrics_to_jsonable(
        compute_metrics(strat.equity, strat.returns, strat.positions)
    )
    print(
        f"  Sharpe={strat_metrics['sharpe']:.3f}  "
        f"return={strat_metrics['total_return']:.2%}  "
        f"maxDD={strat_metrics['max_drawdown']:.2%}  "
        f"hit={strat_metrics['hit_rate']:.2%}  "
        f"final=${strat_metrics['final_equity']:,.0f}"
    )

    print("\n=== Classic TA baselines ===")
    baselines = run_all_baselines(prices, initial_capital=args.capital, warmup=RESEARCH["warmup_bars"])
    for name, res in baselines.items():
        m = metrics_to_jsonable(compute_metrics(res.equity, res.returns, res.positions))
        print(
            f"  {name:20s} Sharpe={m['sharpe']:6.3f}  "
            f"ret={m['total_return']:7.2%}  maxDD={m['max_drawdown']:7.2%}"
        )

    report = build_report(
        strat,
        benchmark=benchmark,
        baseline_results=baselines,
        include_industry=not args.no_industry,
        title=f"strategy_{args.horizon}",
    )
    path = write_report(report, name=f"strategy_{args.horizon}", directory=REPORTS_DIR)
    print(f"\nReport written: {path}")

    if args.portfolio:
        print("\n=== Multi-horizon portfolio ($10k style equity curve) ===")
        port = run_portfolio_backtest(prices, initial_capital=args.capital)
        pm = metrics_to_jsonable(compute_metrics(port.equity, port.returns, port.positions))
        print(
            f"  Sharpe={pm['sharpe']:.3f}  return={pm['total_return']:.2%}  "
            f"maxDD={pm['max_drawdown']:.2%}  final=${pm['final_equity']:,.0f}"
        )
        port_report = build_report(
            port,
            benchmark=benchmark,
            baseline_results={"buy_and_hold": baselines.get("buy_and_hold")}
            if "buy_and_hold" in baselines
            else None,
            include_industry=False,
            title="portfolio_multi_horizon",
        )
        ppath = write_report(port_report, name="portfolio_multi_horizon")
        # Also dump equity CSV for charts
        csv_path = REPORTS_DIR / "latest_portfolio_equity.csv"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        port.equity.to_csv(csv_path, header=["equity"])
        print(f"  Report: {ppath}")
        print(f"  Equity CSV: {csv_path}")

    if args.agent:
        print(f"\n=== Horizon agent loop ({args.horizon}, {args.agent_iters} iters) ===")
        summary = run_horizon_agent(
            prices,
            horizon=args.horizon,
            n_iterations=args.agent_iters,
            initial_capital=args.capital,
            benchmark=benchmark,
            use_llm=bool(__import__("os").environ.get("OPENAI_API_KEY")),
        )
        print(f"  run_dir={summary.run_dir}")
        print(f"  best_iter={summary.best_iteration} test_sharpe={summary.best_test_sharpe:.3f}")
        for art in summary.iterations:
            print(
                f"  iter {art.iteration}: train_sharpe={art.train_metrics.get('sharpe')} "
                f"test_sharpe={art.test_metrics.get('sharpe')}"
            )

    if args.risk_agent:
        print("\n=== Risk agent param ranking ===")
        # Smaller panel for speed
        risk_panel = prices[tickers[:4]] if len(tickers) >= 4 else prices
        ranking = risk_agent_experiment(risk_panel, initial_capital=args.capital)
        for row in ranking.get("ranked") or []:
            m = row["metrics"]
            print(
                f"  {row['variant']:20s} Sharpe={m.get('sharpe', 0):.3f}  "
                f"maxDD={m.get('max_drawdown', 0):.2%}"
            )
        out = REPORTS_DIR / "latest_risk_agent.json"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(ranking, indent=2))
        print(f"  Wrote {out}")

    print("\nDone.")


if __name__ == "__main__":
    main()
