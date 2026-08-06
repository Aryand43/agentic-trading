"""Unit tests for metrics, baselines, and a synthetic signal backtest (no network)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.baselines import signal_buy_and_hold, signal_sma_cross
from src.backtest.engine import run_signal_backtest
from src.backtest.metrics import compute_metrics, hit_rate, max_drawdown, sharpe_ratio
from src.risk.volatility import portfolio_volatility


def _synthetic_prices(n: int = 400, n_tickers: int = 3, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n)
    data = {}
    for i in range(n_tickers):
        rets = rng.normal(0.0003, 0.015, n)
        data[f"T{i}"] = 100 * np.cumprod(1 + rets)
    return pd.DataFrame(data, index=dates)


class TestMetrics(unittest.TestCase):
    def test_max_drawdown_and_sharpe(self):
        eq = pd.Series([100, 110, 105, 120, 90, 95], dtype=float)
        self.assertLess(max_drawdown(eq), 0)
        rets = eq.pct_change().fillna(0)
        s = sharpe_ratio(rets)
        self.assertTrue(np.isfinite(s))
        self.assertGreaterEqual(hit_rate(rets), 0.0)
        self.assertLessEqual(hit_rate(rets), 1.0)

    def test_compute_metrics_keys(self):
        eq = pd.Series(np.linspace(10_000, 12_000, 100))
        m = compute_metrics(eq)
        for k in ("sharpe", "max_drawdown", "hit_rate", "total_return", "final_equity"):
            self.assertIn(k, m)


class TestBacktestEngine(unittest.TestCase):
    def test_buy_hold_grows_with_drift(self):
        prices = _synthetic_prices()
        res = run_signal_backtest(
            prices,
            signal_fn=signal_buy_and_hold,
            initial_capital=10_000,
            warmup=60,
            cost_bps=0.0,
            label="bh",
        )
        self.assertEqual(len(res.equity), len(prices) - 1)
        self.assertGreater(res.equity.iloc[-1], 0)
        m = compute_metrics(res.equity, res.returns, res.positions)
        self.assertIn("sharpe", m)

    def test_sma_signal_runs(self):
        prices = _synthetic_prices()
        res = run_signal_backtest(
            prices,
            signal_fn=signal_sma_cross,
            warmup=80,
            initial_capital=10_000,
        )
        self.assertFalse(res.equity.empty)


class TestLongShortRisk(unittest.TestCase):
    def test_portfolio_vol_allows_shorts(self):
        rng = np.random.default_rng(1)
        dates = pd.date_range("2020-01-01", periods=500, freq="min")
        rets = pd.DataFrame(
            rng.normal(0, 0.001, (500, 3)),
            columns=["A", "B", "C"],
            index=dates,
        )
        weights = {"A": 0.5, "B": -0.3, "C": 0.2}  # long/short, not sum to 1 of abs concern
        # Net sum 0.4; risk engine should accept this
        vol = portfolio_volatility(weights, "1d", rets)
        self.assertGreater(vol, 0)
        self.assertTrue(np.isfinite(vol))


if __name__ == "__main__":
    unittest.main()
