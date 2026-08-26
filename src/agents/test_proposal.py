"""Agent proposal validation tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.proposal import parse_llm_proposal, validate_proposal


class TestAgentProposal(unittest.TestCase):
    def test_rejects_unsafe_params(self):
        with self.assertRaises(Exception):
            validate_proposal({"template": "sma_rsi", "take_profit_pct": 9.0})
        with self.assertRaises(Exception):
            validate_proposal({"template": "not_a_template", "params": {}})
        with self.assertRaises(Exception):
            validate_proposal(
                {"template": "sma_rsi", "take_profit_pct": 0.01, "stop_loss_pct": 0.20}
            )

    def test_accepts_bounded_json(self):
        parsed = parse_llm_proposal(
            '```json\n{"template": "reversal", "params": {"lookback": 12}, '
            '"take_profit_pct": 0.06, "stop_loss_pct": 0.03}\n```'
        )
        self.assertIsNotNone(parsed)
        prop = validate_proposal(parsed)
        self.assertEqual(prop.template, "reversal")
        self.assertEqual(prop.take_profit_pct, 0.06)


if __name__ == "__main__":
    unittest.main()
