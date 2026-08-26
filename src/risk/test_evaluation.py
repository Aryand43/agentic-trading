"""Walk-forward risk comparison tests (daily bars, no look-ahead)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.evaluation import evaluate_risk_methods


class TestRiskEvaluation(unittest.TestCase):
    def test_predicted_uses_only_past_and_reports_breach(self):
        rng = np.random.default_rng(0)
        n = 400
        rets = pd.Series(rng.normal(0, 0.01, n), index=pd.bdate_range("2018-01-01", periods=n))
        rows = evaluate_risk_methods(rets, horizons=["1d", "5d"], window=60, min_obs=30)
        self.assertTrue(rows)
        methods = {r["method"] for r in rows}
        self.assertIn("historical_std", methods)
        self.assertIn("historical_var", methods)
        self.assertIn("ewma_cornish_fisher", methods)
        for row in rows:
            self.assertGreater(row["n_obs"], 0)
            self.assertIsNotNone(row["sample_start"])
            self.assertIsNotNone(row["sample_end"])
            if row["method"] != "historical_std":
                self.assertIsNotNone(row["breach_rate"])
                self.assertGreaterEqual(row["breach_rate"], 0.0)
                self.assertLessEqual(row["breach_rate"], 1.0)

    def test_empty_returns_empty_table(self):
        self.assertEqual(evaluate_risk_methods(pd.Series(dtype=float)), [])


if __name__ == "__main__":
    unittest.main()
