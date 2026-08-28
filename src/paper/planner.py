"""LLM planner for paper experiments. Fallback is the frozen protocol."""

from __future__ import annotations

import json

from src.agents.llm import llm_chat
from src.agents.proposal import parse_llm_proposal
from src.config import HORIZONS, NASDAQ_UNIVERSE, PAPER_PROTOCOL
from src.paper.spec import ExperimentSpec, frozen_protocol

_PLANNER_SYSTEM = (
    "You plan a historical backtest experiment. Reply with JSON only. "
    "Do not invent signals, tickers, or live trades. Stay inside the allowlists."
)


def _planner_user() -> str:
    return (
        "Propose a paper backtest spec as JSON with keys: "
        "tickers (subset of "
        + json.dumps(list(NASDAQ_UNIVERSE))
        + "), period (3y or 5y), horizons (subset of "
        + json.dumps(list(HORIZONS))
        + "), include_agent (bool), n_iterations (1-5), test_days (15-126), "
        "agent_horizons (subset of horizons; prefer [\"10d\"] for a first sweep). "
        "Default protocol: "
        + json.dumps(PAPER_PROTOCOL)
        + ". Prefer the default unless you have a reason to shrink the universe. "
        "This is not live trading."
    )


def plan_experiment(*, force: bool = False) -> ExperimentSpec:
    """Frozen protocol unless ``force`` is set, then LLM with fallback."""
    if not force:
        return frozen_protocol(source="fallback")
    text = llm_chat(_PLANNER_SYSTEM, _planner_user())
    payload = parse_llm_proposal(text or "")
    if not payload:
        return frozen_protocol(source="fallback")
    try:
        return ExperimentSpec.model_validate({**payload, "source": "llm"})
    except Exception:
        return frozen_protocol(source="fallback")
