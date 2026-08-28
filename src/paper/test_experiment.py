"""Experiment spec, planner fallback, and table-writer smoke tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.paper.experiment import run_paper_experiment
from src.paper.planner import plan_experiment
from src.paper.spec import ExperimentSpec, frozen_protocol


def _panel(n=400, tickers=("AAPL", "MSFT"), seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n)
    close = pd.DataFrame(
        {t: 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, n)) for t in tickers},
        index=dates,
    )
    open_px = close.shift(1).bfill() * 1.0001
    high = np.maximum(close, open_px) * 1.005
    low = np.minimum(close, open_px) * 0.995
    return {"Close": close, "Open": open_px, "High": high, "Low": low}


class TestExperimentSpec(unittest.TestCase):
    def test_rejects_unknown_tickers(self):
        with self.assertRaises(Exception):
            ExperimentSpec(tickers=["NOTREAL"])

    def test_rejects_test_days_out_of_range(self):
        with self.assertRaises(Exception):
            ExperimentSpec(test_days=5)
        with self.assertRaises(Exception):
            ExperimentSpec(test_days=200)

    def test_frozen_protocol_valid(self):
        spec = frozen_protocol()
        self.assertEqual(spec.period, "5y")
        self.assertEqual(spec.test_days, 63)
        self.assertEqual(spec.agent_horizons, ["10d"])


class TestPlannerFallback(unittest.TestCase):
    def test_default_is_frozen(self):
        spec = plan_experiment(force=False)
        self.assertEqual(spec.source, "fallback")
        self.assertEqual(spec.test_days, 63)

    def test_garbage_llm_falls_back(self):
        with patch("src.paper.planner.llm_chat", return_value="not json at all"):
            spec = plan_experiment(force=True)
        self.assertEqual(spec.source, "fallback")

    def test_invalid_spec_falls_back(self):
        with patch(
            "src.paper.planner.llm_chat",
            return_value='{"tickers": ["FAKETICKER"], "period": "5y"}',
        ):
            spec = plan_experiment(force=True)
        self.assertEqual(spec.source, "fallback")

    def test_valid_llm_spec(self):
        with patch(
            "src.paper.planner.llm_chat",
            return_value='{"tickers": ["AAPL", "MSFT"], "period": "3y", '
            '"horizons": ["10d"], "include_agent": false, "n_iterations": 1, '
            '"test_days": 21, "agent_horizons": ["10d"]}',
        ):
            spec = plan_experiment(force=True)
        self.assertEqual(spec.source, "llm")
        self.assertEqual(spec.period, "3y")
        self.assertEqual(spec.tickers, ["AAPL", "MSFT"])
        self.assertFalse(spec.include_agent)


class TestRunnerTables(unittest.TestCase):
    def test_writes_core_tables(self):
        ohlc = _panel()
        spec = ExperimentSpec(
            tickers=["AAPL", "MSFT"],
            period="5y",
            horizons=["1d", "10d"],
            include_agent=False,
            n_iterations=1,
            test_days=21,
            agent_horizons=["10d"],
            source="explicit",
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = run_paper_experiment(
                spec,
                ohlc=ohlc,
                benchmark=ohlc["Close"].mean(axis=1),
                output_dir=Path(tmp) / "paper",
                include_industry=False,
                use_llm=False,
            )
            tables = out / "tables"
            self.assertTrue((tables / "strategy_vs_baselines.csv").exists())
            self.assertTrue((tables / "strategy_vs_baselines.md").exists())
            self.assertTrue((tables / "risk_comparison.csv").exists())
            self.assertTrue((tables / "risk_comparison.md").exists())
            self.assertTrue((tables / "segments.csv").exists())
            self.assertTrue((tables / "segments.md").exists())
            self.assertTrue((out / "README.md").exists())
            self.assertTrue((out / "spec.json").exists())
            self.assertTrue((out / "portfolio" / "trades.csv").exists())
            self.assertFalse((tables / "agent_leaderboard.csv").exists())


if __name__ == "__main__":
    unittest.main()
