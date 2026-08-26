"""Typed trading configuration for auditable, point-in-time backtests.

Timing (no look-ahead)
----------------------
- A signal at calendar/session date T may use OHLCV through T's close only.
- Execution lags by ``signal_lag_bars`` (default 1): a 1-day signal trades at
  T+1 open when Open is available.
- Multi-day horizons target the close at T+h relative to T+1 open, where h is
  ``HORIZON_TRADING_DAYS[horizon]``.
- Take-profit / stop-loss are checked on the next session's high/low after
  entry (and on each subsequent bar). They never use future bars.
- If Open/High/Low are missing, fills use the next available close and
  ``price_source`` is recorded as ``close``. Prices are never fabricated.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.config import HORIZON_TRADING_DAYS, HORIZONS, RESEARCH

TIMING_NOTES = (
    "Signals at T use information available at T only (OHLCV through T close). "
    "A 1-day signal trades at T+1 open when Open is available. Multi-day "
    "signals target the close at T+h after entering at T+1 open. Take-profit "
    "and stop-loss triggers use that bar's high/low; if the open gaps through "
    "the level the fill is the open, otherwise the threshold. Horizon, "
    "rebalance, and end-of-data exits use close. Missing Open/High/Low are "
    "not invented: the next available close is used and price_source=close."
)


class SideMode(str, Enum):
    long_only = "long_only"
    long_short = "long_short"


class TradingRules(BaseModel):
    """Explicit, serializable trading rules for one backtest run."""

    model_config = {"extra": "forbid"}

    horizons: list[str] = Field(default_factory=lambda: list(HORIZONS))
    signal_lag_bars: int = Field(default=1, ge=1, le=5)
    entry_price_field: str = Field(default="open")
    take_profit_pct: float = Field(default=0.08, ge=0.0, le=1.0)
    stop_loss_pct: float = Field(default=0.04, ge=0.0, le=1.0)
    max_holding_bars: dict[str, int] = Field(default_factory=dict)
    side_mode: SideMode = Field(default=SideMode.long_short)
    rebalance_every: int = Field(default=5, ge=1, le=63)
    cost_bps: float = Field(default=5.0, ge=0.0, le=200.0)
    slippage_bps: float = Field(default=0.0, ge=0.0, le=200.0)
    long_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    short_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    max_position: float = Field(default=0.15, ge=0.01, le=1.0)
    gross_exposure: float = Field(default=1.0, ge=0.01, le=5.0)
    initial_capital: float = Field(default=10_000.0, ge=100.0)
    warmup_bars: int = Field(default=260, ge=5)
    target_volatility: Optional[float] = Field(default=0.15, ge=0.01, le=1.0)
    max_leverage: float = Field(default=2.0, ge=0.1, le=10.0)
    timing_notes: str = Field(default=TIMING_NOTES)

    @field_validator("horizons")
    @classmethod
    def _known_horizons(cls, value: list[str]) -> list[str]:
        unknown = [h for h in value if h not in HORIZONS]
        if unknown:
            raise ValueError(f"Unknown horizon(s): {unknown}. Choose from {HORIZONS}.")
        if not value:
            raise ValueError("horizons must be non-empty.")
        return list(value)

    @field_validator("entry_price_field")
    @classmethod
    def _entry_field(cls, value: str) -> str:
        allowed = {"open", "close"}
        if value not in allowed:
            raise ValueError(f"entry_price_field must be one of {allowed}.")
        return value

    @field_validator("side_mode", mode="before")
    @classmethod
    def _side_mode(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def _holding_defaults(self) -> TradingRules:
        holding = dict(self.max_holding_bars)
        for horizon in self.horizons:
            if horizon not in holding:
                holding[horizon] = int(HORIZON_TRADING_DAYS[horizon])
            if holding[horizon] < 1:
                raise ValueError(f"max_holding_bars[{horizon}] must be >= 1.")
        self.max_holding_bars = holding
        return self

    def holding_bars(self, horizon: str) -> int:
        if horizon in self.max_holding_bars:
            return int(self.max_holding_bars[horizon])
        if horizon not in HORIZON_TRADING_DAYS:
            raise ValueError(f"Unknown horizon: {horizon}")
        return int(HORIZON_TRADING_DAYS[horizon])

    def cost_rate(self) -> float:
        return (self.cost_bps + self.slippage_bps) / 10_000.0

    def to_jsonable(self) -> dict[str, Any]:
        data = self.model_dump()
        data["side_mode"] = self.side_mode.value
        return data


def default_trading_rules(**overrides: Any) -> TradingRules:
    """Build rules from RESEARCH defaults plus optional overrides."""
    base: dict[str, Any] = {
        "horizons": list(HORIZONS),
        "rebalance_every": int(RESEARCH.get("rebalance_every", 5)),
        "cost_bps": float(RESEARCH.get("cost_bps", 5.0)),
        "slippage_bps": float(RESEARCH.get("slippage_bps", 0.0)),
        "take_profit_pct": float(RESEARCH.get("take_profit_pct", 0.08)),
        "stop_loss_pct": float(RESEARCH.get("stop_loss_pct", 0.04)),
        "side_mode": RESEARCH.get("side_mode", "long_short"),
        "long_threshold": float(RESEARCH.get("long_threshold", 0.05)),
        "short_threshold": float(RESEARCH.get("short_threshold", 0.05)),
        "initial_capital": float(RESEARCH.get("initial_capital", 10_000.0)),
        "warmup_bars": int(RESEARCH.get("warmup_bars", 260)),
    }
    base.update({k: v for k, v in overrides.items() if v is not None})
    return TradingRules(**base)
