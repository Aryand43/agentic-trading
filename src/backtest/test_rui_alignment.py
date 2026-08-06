"""Unit tests for Rui-aligned metrics and splits."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.backtest.metrics import signal_hit_rate, strategy_utility
from src.backtest.splits import split_train_val_test


class TestRuiMetrics(unittest.TestCase):
    def test_signal_hit_rate_buy_sell(self):
        # +signal correct, -signal correct, flat ignored
        sig = pd.Series([1.0, 1.0, -1.0, 0.0, -1.0])
        fwd = pd.Series([0.02, -0.01, -0.02, 0.05, 0.03])  # last sell wrong
        # active: 4 cases? wait flat ignored so 4 signals: buy ok, buy wrong, sell ok, sell wrong → 0.5
        h = signal_hit_rate(sig, fwd, flat_threshold=0.05)
        self.assertAlmostEqual(h, 0.5)

    def test_utility_bounds(self):
        u = strategy_utility(0.6, 0.1)
        self.assertGreater(u, 0.4)
        self.assertLess(u, 1.0)


class TestSplits(unittest.TestCase):
    def test_split_order(self):
        idx = pd.bdate_range("2020-01-01", periods=900)
        px = pd.DataFrame({"A": np.linspace(100, 200, len(idx))}, index=idx)
        sp = split_train_val_test(px, train_days=756, val_days=126, test_days=15)
        self.assertEqual(sp.n_test, 15)
        self.assertEqual(sp.n_val, 126)
        self.assertLessEqual(sp.n_train, 756)
        self.assertLess(sp.train.index.max(), sp.val.index.min())
        self.assertLess(sp.val.index.max(), sp.test.index.min())


if __name__ == "__main__":
    unittest.main()
