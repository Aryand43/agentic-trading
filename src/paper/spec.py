"""Bounded paper-experiment specification."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.config import HORIZONS, NASDAQ_UNIVERSE, PAPER_PROTOCOL

ALLOWED_PERIODS = ("3y", "5y")
ALLOWED_TICKERS = frozenset(NASDAQ_UNIVERSE)


class ExperimentSpec(BaseModel):
    """What to run. The LLM may fill this; engines execute it."""

    model_config = {"extra": "ignore"}

    tickers: list[str] = Field(default_factory=lambda: list(PAPER_PROTOCOL["tickers"]))
    period: Literal["3y", "5y"] = "5y"
    horizons: list[str] = Field(default_factory=lambda: list(HORIZONS))
    include_agent: bool = True
    n_iterations: int = Field(default=2, ge=1, le=5)
    test_days: int = Field(default=63, ge=15, le=126)
    agent_horizons: list[str] = Field(default_factory=lambda: ["10d"])
    source: str = "explicit"

    @field_validator("tickers")
    @classmethod
    def _tickers(cls, value: list[str]) -> list[str]:
        names = [str(t).strip().upper() for t in value if str(t).strip()]
        unknown = [t for t in names if t not in ALLOWED_TICKERS]
        if unknown:
            raise ValueError(f"Unknown ticker(s) {unknown}. Choose from {sorted(ALLOWED_TICKERS)}.")
        if not names:
            raise ValueError("tickers must be non-empty.")
        # preserve order, drop dupes
        seen: set[str] = set()
        out: list[str] = []
        for t in names:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    @field_validator("horizons", "agent_horizons")
    @classmethod
    def _horizons(cls, value: list[str]) -> list[str]:
        names = [str(h).strip() for h in value if str(h).strip()]
        unknown = [h for h in names if h not in HORIZONS]
        if unknown:
            raise ValueError(f"Unknown horizon(s) {unknown}. Choose from {HORIZONS}.")
        if not names:
            raise ValueError("horizons must be non-empty.")
        return names

    @field_validator("period")
    @classmethod
    def _period(cls, value: str) -> str:
        p = str(value).strip().lower()
        if p not in ALLOWED_PERIODS:
            raise ValueError(f"period must be one of {ALLOWED_PERIODS}.")
        return p

    @model_validator(mode="after")
    def _agent_horizons_subset(self) -> ExperimentSpec:
        extra = [h for h in self.agent_horizons if h not in self.horizons]
        if extra:
            self.agent_horizons = [h for h in self.agent_horizons if h in self.horizons]
            if not self.agent_horizons:
                self.agent_horizons = [self.horizons[0]]
        return self


def frozen_protocol(*, source: str = "fallback") -> ExperimentSpec:
    return ExperimentSpec.model_validate({**PAPER_PROTOCOL, "source": source})


def spec_to_jsonable(spec: ExperimentSpec) -> dict[str, Any]:
    return spec.model_dump()
