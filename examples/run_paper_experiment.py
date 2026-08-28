"""CLI: LLM-planned (or frozen) paper backtest → empirical tables.

    python -m examples.run_paper_experiment
    python -m examples.run_paper_experiment --plan
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.paper.experiment import run_paper_experiment
from src.paper.planner import plan_experiment
from src.paper.spec import ExperimentSpec


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper experiment: backtest + empirical tables")
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Ask the LLM to fill ExperimentSpec (falls back to frozen protocol)",
    )
    parser.add_argument("--no-agent", action="store_true", help="Skip the horizon discovery loop")
    parser.add_argument(
        "--horizon",
        type=str,
        default=None,
        help="Agent horizon override (default from spec, usually 10d)",
    )
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--no-industry", action="store_true", help="Skip yfinance sector lookup")
    args = parser.parse_args()

    spec: ExperimentSpec = plan_experiment(force=args.plan)
    updates: dict = {}
    if args.no_agent:
        updates["include_agent"] = False
    if args.horizon:
        updates["agent_horizons"] = [args.horizon.strip()]
        if args.horizon.strip() not in spec.horizons:
            updates["horizons"] = list(spec.horizons) + [args.horizon.strip()]
    if updates:
        spec = spec.model_copy(update=updates)

    print(
        f"Spec source={spec.source} period={spec.period} "
        f"tickers={len(spec.tickers)} agent={spec.include_agent}"
    )
    out = run_paper_experiment(
        spec,
        plan=False,
        use_cache=not args.no_cache,
        include_industry=False if args.no_industry else None,
        use_llm=bool(spec.include_agent),
    )
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
