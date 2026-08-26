"""Typed, bounded agent proposals. Never applied to live /api/run."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.config import RESEARCH

ALLOWED_RISK_METHODS = (
    "historical_std",
    "historical_var",
    "ewma_cornish_fisher",
)
ALLOWED_TEMPLATES = (
    "sma_rsi",
    "bollinger_squeeze",
    "reversal",
    "momentum_skip",
    "buy_and_hold",
    "sma_cross",
    "rsi_mean_reversion",
    "momentum_20d",
)


class AgentProposal(BaseModel):
    """Validated research-only parameter proposal."""

    model_config = {"extra": "ignore"}

    template: str
    params: dict[str, float] = Field(default_factory=dict)
    take_profit_pct: Optional[float] = Field(default=None, ge=0.0, le=0.25)
    stop_loss_pct: Optional[float] = Field(default=None, ge=0.0, le=0.25)
    rebalance_every: Optional[int] = Field(default=None, ge=1, le=21)
    max_position: Optional[float] = Field(default=None, ge=0.01, le=0.50)
    gross_exposure: Optional[float] = Field(default=None, ge=0.05, le=2.0)
    target_volatility: Optional[float] = Field(default=None, ge=0.05, le=0.40)
    risk_method: Optional[str] = None
    description: str = ""

    @field_validator("template")
    @classmethod
    def _template(cls, value: str) -> str:
        name = value.strip()
        if name not in ALLOWED_TEMPLATES:
            raise ValueError(f"Unknown template {name!r}. Choose from {ALLOWED_TEMPLATES}.")
        return name

    @field_validator("risk_method")
    @classmethod
    def _risk(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        if value not in ALLOWED_RISK_METHODS:
            raise ValueError(f"Unknown risk_method {value!r}. Choose from {ALLOWED_RISK_METHODS}.")
        return value

    @model_validator(mode="after")
    def _tp_sl_order(self) -> AgentProposal:
        if (
            self.take_profit_pct is not None
            and self.stop_loss_pct is not None
            and self.take_profit_pct < self.stop_loss_pct
        ):
            raise ValueError("take_profit_pct must be >= stop_loss_pct.")
        return self


def clip_params_to_bounds(template: str, params: dict[str, float], bounds: dict) -> dict[str, float]:
    out = dict(params)
    for key, pair in (bounds or {}).items():
        lo, hi = pair
        if key in out:
            out[key] = float(min(hi, max(lo, out[key])))
    return out


def parse_llm_proposal(text: str) -> Optional[dict[str, Any]]:
    """Extract a JSON object from an LLM reply, or None."""
    if not text:
        return None
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    blob = fence.group(1) if fence else None
    if blob is None:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            blob = stripped[start : end + 1]
    if not blob:
        return None
    try:
        payload = json.loads(blob)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def validate_proposal(payload: dict[str, Any], *, template_bounds: dict | None = None) -> AgentProposal:
    proposal = AgentProposal.model_validate(payload)
    if template_bounds:
        proposal.params = clip_params_to_bounds(
            proposal.template, proposal.params, template_bounds
        )
    return proposal


def default_rules_from_proposal(proposal: AgentProposal) -> dict[str, Any]:
    """Map a proposal onto run_signal_backtest kwargs. Live desk is untouched."""
    out: dict[str, Any] = {}
    if proposal.take_profit_pct is not None:
        out["take_profit_pct"] = proposal.take_profit_pct
    if proposal.stop_loss_pct is not None:
        out["stop_loss_pct"] = proposal.stop_loss_pct
    if proposal.rebalance_every is not None:
        out["rebalance_every"] = proposal.rebalance_every
    if proposal.max_position is not None:
        out["max_position"] = proposal.max_position
    return out


def build_observation(
    *,
    test_metrics: dict[str, Any],
    train_metrics: dict[str, Any],
    val_metrics: dict[str, Any],
    trades: list | None = None,
    risk_comparison: list | None = None,
    trading_rules: dict | None = None,
    prior: list | None = None,
    var_breach_rate: float | None = None,
) -> dict[str, Any]:
    trade_list = trades or []
    pnls = [getattr(t, "net_pnl", None) if not isinstance(t, dict) else t.get("net_pnl") for t in trade_list]
    pnls = [float(p) for p in pnls if p is not None]
    wins = sum(1 for p in pnls if p > 0)
    reasons: dict[str, int] = {}
    for t in trade_list:
        reason = getattr(t, "exit_reason", None) if not isinstance(t, dict) else t.get("exit_reason")
        if hasattr(reason, "value"):
            reason = reason.value
        if reason:
            reasons[str(reason)] = reasons.get(str(reason), 0) + 1
    audit_ok = all(
        (getattr(t, "trade_id", None) if not isinstance(t, dict) else t.get("trade_id"))
        and (getattr(t, "signal_horizon", None) if not isinstance(t, dict) else t.get("signal_horizon"))
        for t in trade_list
    ) if trade_list else True
    return {
        "train_metrics": train_metrics,
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "drawdown": test_metrics.get("max_drawdown"),
        "turnover": test_metrics.get("turnover"),
        "var_breach_rate": var_breach_rate,
        "trade_stats": {
            "n_trades": len(trade_list),
            "win_rate": (wins / len(pnls)) if pnls else None,
            "mean_net_pnl": (sum(pnls) / len(pnls)) if pnls else None,
            "exit_reasons": reasons,
        },
        "risk_comparison": risk_comparison or [],
        "auditability": {"complete_trade_ids": audit_ok, "n_trades": len(trade_list)},
        "trading_rules": trading_rules or {
            "rebalance_every": RESEARCH.get("rebalance_every"),
            "cost_bps": RESEARCH.get("cost_bps"),
            "take_profit_pct": RESEARCH.get("take_profit_pct"),
            "stop_loss_pct": RESEARCH.get("stop_loss_pct"),
        },
        "prior_hypotheses": prior or [],
    }
