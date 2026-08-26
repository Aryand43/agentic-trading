"""API schema compatibility: old fields remain on BacktestResponse."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@unittest.skipIf(sys.version_info < (3, 10), "API schemas require Python 3.10+")
class TestApiCompat(unittest.TestCase):
    def test_legacy_backtest_payload_still_validates(self):
        from api.schemas import BacktestResponse, MetricsBlock

        payload = {
            "tickers": ["AAPL"],
            "initial_capital": 10000,
            "window": {"start": "2020-01-01", "end": "2023-01-01", "n_days": 750},
            "metrics": MetricsBlock().model_dump(),
            "equity_curve": [{"date": "2020-01-02", "equity": 10000, "series": "strategy"}],
        }
        model = BacktestResponse.model_validate(payload)
        self.assertEqual(model.tickers, ["AAPL"])
        self.assertEqual(model.portfolios, {})
        self.assertEqual(model.trades, [])
        self.assertIsNone(model.run_id)

    def test_get_trades_missing_run(self):
        from api.service import get_backtest_trades

        with self.assertRaises(FileNotFoundError):
            get_backtest_trades("does-not-exist")


if __name__ == "__main__":
    unittest.main()
