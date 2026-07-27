"""Request / response shapes for the dashboard API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    tickers: list[str] | None = Field(
        default=None,
        description="Optional override; defaults to TRADING tickers in config.",
    )
    max_position: float = Field(default=0.15, ge=0.01, le=1.0)
    gross_exposure: float = Field(default=1.0, ge=0.01, le=5.0)
    target_volatility: float | None = Field(
        default=None,
        description="Optional override of pipeline default target volatility.",
    )


class RunResponse(BaseModel):
    tickers: list[str]
    horizons: list[str]
    signals: dict[str, dict[str, float]]
    conviction: dict[str, float]
    volatilities: dict[str, float]
    portfolio_volatility: float
    target_volatility: float
    weights: dict[str, float]
