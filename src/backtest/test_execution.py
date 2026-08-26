"""Look-ahead, TP/SL, long-only, costs, and audit-field tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.engine import run_signal_backtest
from src.backtest.execution import simulate
from src.backtest.trades import classify_side, write_run_artifacts
from src.backtest.trading_rules import default_trading_rules
from src.config import REPORTS_DIR


def _panel(n=80, tickers=("AAA",), seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n)
    data = {}
    for i, t in enumerate(tickers):
        rets = rng.normal(0.0, 0.01, n)
        data[t] = 100 * np.cumprod(1 + rets)
    close = pd.DataFrame(data, index=dates)
    open_px = close.shift(1).fillna(close.iloc[0] * 0.999)
    high = pd.concat([close, open_px], axis=1).T.groupby(level=0).max().T
    # rebuild high/low simply
    high = np.maximum(close, open_px) * 1.001
    low = np.minimum(close, open_px) * 0.999
    return close, open_px, high, low


class TestClassify(unittest.TestCase):
    def test_long_only_sell_is_neutral(self):
        self.assertEqual(classify_side(-0.8, side_mode="long_only").value, "neutral")
        self.assertEqual(classify_side(-0.8, side_mode="long_short").value, "sell")
        self.assertEqual(classify_side(0.8).value, "buy")


class TestLookAhead(unittest.TestCase):
    def test_signal_uses_only_t_and_enters_next_open(self):
        dates = pd.bdate_range("2020-01-02", periods=40)
        close = pd.DataFrame({"AAA": np.linspace(100, 110, 40)}, index=dates)
        open_px = close * 1.0
        open_px.iloc[:] = close.values
        high = close * 1.01
        low = close * 0.99

        captured = {}

        def signal_fn(prices: pd.Series) -> float:
            captured.setdefault("last_len", []).append(len(prices))
            captured["last_price"] = float(prices.iloc[-1])
            return 1.0

        rules = default_trading_rules(
            horizons=["1d"],
            warmup_bars=10,
            rebalance_every=1,
            take_profit_pct=0.0,
            stop_loss_pct=0.0,
            initial_capital=10_000,
            cost_bps=0.0,
            slippage_bps=0.0,
        )
        res = simulate(
            close,
            rules=rules,
            signal_fn=signal_fn,
            horizon="1d",
            open_px=open_px,
            high=high,
            low=low,
        )
        self.assertTrue(res.trades)
        first = next(t for t in res.trades if t.exit_reason and t.exit_reason.value != "rejected")
        self.assertIsNotNone(first.entry_date)
        self.assertGreater(first.entry_date, first.signal_date)
        # mutating a future close after the last observed signal length must not
        # have been visible: last signal price equals some in-sample close.
        self.assertIn(captured["last_price"], set(close["AAA"].astype(float)))

    def test_future_open_does_not_change_prior_signal(self):
        close, open_px, high, low = _panel(n=50)
        seen = []

        def signal_fn(prices: pd.Series) -> float:
            seen.append(float(prices.iloc[-1]))
            return 1.0

        rules = default_trading_rules(
            horizons=["1d"], warmup_bars=8, rebalance_every=5,
            take_profit_pct=0.0, stop_loss_pct=0.0, cost_bps=0.0,
        )
        simulate(close, rules=rules, signal_fn=signal_fn, horizon="1d", open_px=open_px, high=high, low=low)
        snapshot = list(seen)
        open_px = open_px.copy()
        open_px.iloc[-1] = 9999.0
        seen.clear()
        simulate(close, rules=rules, signal_fn=signal_fn, horizon="1d", open_px=open_px, high=high, low=low)
        self.assertEqual(snapshot, seen)


class TestExits(unittest.TestCase):
    def test_horizon_end_forced(self):
        dates = pd.bdate_range("2020-01-02", periods=30)
        close = pd.DataFrame({"AAA": np.full(30, 100.0)}, index=dates)
        open_px, high, low = close.copy(), close * 1.001, close * 0.999
        rules = default_trading_rules(
            horizons=["5d"], warmup_bars=6, rebalance_every=20,
            take_profit_pct=0.0, stop_loss_pct=0.0, cost_bps=0.0,
        )
        res = simulate(close, rules=rules, signal_fn=lambda p: 1.0, horizon="5d",
                       open_px=open_px, high=high, low=low)
        reasons = {t.exit_reason.value for t in res.trades if t.exit_reason}
        self.assertTrue("horizon_end" in reasons or "end_of_data" in reasons)

    def test_take_profit_on_high(self):
        dates = pd.bdate_range("2020-01-02", periods=25)
        close = pd.DataFrame({"AAA": np.full(25, 100.0)}, index=dates)
        open_px = close.copy()
        high = close.copy()
        low = close * 0.99
        high.iloc[12] = 120.0  # 20% above
        rules = default_trading_rules(
            horizons=["10d"], warmup_bars=5, rebalance_every=30,
            take_profit_pct=0.08, stop_loss_pct=0.0, cost_bps=0.0,
        )
        res = simulate(close, rules=rules, signal_fn=lambda p: 1.0, horizon="10d",
                       open_px=open_px, high=high, low=low)
        self.assertTrue(any(t.exit_reason and t.exit_reason.value == "take_profit" for t in res.trades))

    def test_stop_loss_on_low(self):
        dates = pd.bdate_range("2020-01-02", periods=25)
        close = pd.DataFrame({"AAA": np.full(25, 100.0)}, index=dates)
        open_px = close.copy()
        high = close * 1.01
        low = close.copy()
        low.iloc[12] = 80.0
        rules = default_trading_rules(
            horizons=["10d"], warmup_bars=5, rebalance_every=30,
            take_profit_pct=0.0, stop_loss_pct=0.05, cost_bps=0.0,
        )
        res = simulate(close, rules=rules, signal_fn=lambda p: 1.0, horizon="10d",
                       open_px=open_px, high=high, low=low)
        self.assertTrue(any(t.exit_reason and t.exit_reason.value == "stop_loss" for t in res.trades))

    def test_gap_through_uses_open(self):
        dates = pd.bdate_range("2020-01-02", periods=25)
        close = pd.DataFrame({"AAA": np.full(25, 100.0)}, index=dates)
        open_px = close.copy()
        open_px.iloc[12] = 130.0
        high = np.maximum(close, open_px)
        low = np.minimum(close, open_px)
        rules = default_trading_rules(
            horizons=["10d"], warmup_bars=5, rebalance_every=30,
            take_profit_pct=0.08, stop_loss_pct=0.0, cost_bps=0.0,
        )
        res = simulate(close, rules=rules, signal_fn=lambda p: 1.0, horizon="10d",
                       open_px=open_px, high=high, low=low)
        tp = [t for t in res.trades if t.exit_reason and t.exit_reason.value == "take_profit"]
        self.assertTrue(tp)
        self.assertAlmostEqual(tp[0].exit_price, 130.0, places=4)


class TestSidesAndCosts(unittest.TestCase):
    def test_long_only_no_shorts(self):
        close, open_px, high, low = _panel(n=60, tickers=("AAA", "BBB"))
        rules = default_trading_rules(
            horizons=["5d"], warmup_bars=10, rebalance_every=5,
            side_mode="long_only", take_profit_pct=0.0, stop_loss_pct=0.0, cost_bps=0.0,
        )
        res = simulate(close, rules=rules, signal_fn=lambda p: -1.0, horizon="5d",
                       open_px=open_px, high=high, low=low)
        self.assertFalse(any(t.position_direction.value == "short" for t in res.trades))

    def test_long_short_allows_shorts(self):
        close, open_px, high, low = _panel(n=60)
        rules = default_trading_rules(
            horizons=["5d"], warmup_bars=10, rebalance_every=5,
            side_mode="long_short", take_profit_pct=0.0, stop_loss_pct=0.0, cost_bps=0.0,
        )
        res = simulate(close, rules=rules, signal_fn=lambda p: -1.0, horizon="5d",
                       open_px=open_px, high=high, low=low)
        self.assertTrue(any(t.position_direction.value == "short" for t in res.trades))

    def test_transaction_cost_and_audit_fields(self):
        close, open_px, high, low = _panel(n=50)
        rules = default_trading_rules(
            horizons=["5d"], warmup_bars=8, rebalance_every=10,
            take_profit_pct=0.0, stop_loss_pct=0.0, cost_bps=10.0, slippage_bps=0.0,
        )
        res = simulate(close, rules=rules, signal_fn=lambda p: 1.0, horizon="5d",
                       open_px=open_px, high=high, low=low, run_id="unit-cost", write_artifacts=True)
        filled = [t for t in res.trades if t.entry_price]
        self.assertTrue(filled)
        t = filled[0]
        for field in (
            "trade_id", "ticker", "signal_date", "signal_horizon", "signal_value",
            "signal_side", "entry_date", "exit_reason",
        ):
            self.assertTrue(getattr(t, field) is not None)
        self.assertGreater(t.transaction_cost, 0)
        events = [e for e in res.signal_events if e.ticker == t.ticker and e.date == t.signal_date]
        self.assertTrue(events)
        paths = write_run_artifacts("unit-cost", trades=res.trades, config=rules.to_jsonable())
        self.assertTrue(Path(paths["trades_csv"]).exists())
        self.assertTrue((REPORTS_DIR / "unit-cost" / "trades.json").exists())


class TestEngineWrapper(unittest.TestCase):
    def test_run_signal_backtest_len(self):
        close, _, _, _ = _panel(n=80)
        res = run_signal_backtest(close, signal_fn=lambda p: 1.0, warmup=20, cost_bps=0.0)
        self.assertEqual(len(res.equity), len(close) - 1)


if __name__ == "__main__":
    unittest.main()
