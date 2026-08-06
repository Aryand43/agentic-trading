"""CLI: single-horizon strategy discovery agent.

    python -m examples.run_agent --horizon 10d --iters 3
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.horizon_agent import run_horizon_agent
from src.config import RESEARCH
from src.risk.engine.data_loader import fetch_benchmark, fetch_research_prices


def main() -> None:
    parser = argparse.ArgumentParser(description="Horizon strategy discovery agent")
    parser.add_argument("--horizon", default="10d")
    parser.add_argument("--iters", type=int, default=3)
    parser.add_argument("--tickers", default=",".join(RESEARCH["tickers"][:8]))
    parser.add_argument("--period", default=RESEARCH["period"])
    parser.add_argument("--capital", type=float, default=RESEARCH["initial_capital"])
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    prices = fetch_research_prices(tickers, period=args.period)
    try:
        benchmark = fetch_benchmark(period=args.period)
    except Exception:
        benchmark = None

    summary = run_horizon_agent(
        prices,
        horizon=args.horizon,
        n_iterations=args.iters,
        initial_capital=args.capital,
        benchmark=benchmark,
        use_llm=bool(os.environ.get("OPENAI_API_KEY")),
    )
    print(f"run_dir={summary.run_dir}")
    print(f"best_iteration={summary.best_iteration} best_test_sharpe={summary.best_test_sharpe:.3f}")
    for art in summary.iterations:
        print("---")
        print(f"iter {art.iteration} hash={art.code_hash}")
        print(f"  hyp: {art.hypothesis.description[:200]}")
        print(f"  train sharpe={art.train_metrics.get('sharpe')}")
        print(f"  test  sharpe={art.test_metrics.get('sharpe')}")
        print(f"  insights: {art.insights[:300]}")


if __name__ == "__main__":
    main()
