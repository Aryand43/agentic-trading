"""Orchestrates existing pipeline modules — no backend logic lives here."""

from __future__ import annotations

from src.config import HORIZONS, TRADING
from src.portfolio.construction import combine_horizon_signals, construct_portfolio

from examples.load_pipeline_data import load_pipeline_data

from api.schemas import RunRequest, RunResponse


def run_pipeline(request: RunRequest) -> RunResponse:
    tickers = request.tickers or list(TRADING["tickers"])

    kwargs: dict = {"tickers": tickers}
    if request.target_volatility is not None:
        kwargs["target_volatility"] = request.target_volatility

    signals, volatilities, port_vol, target_vol = load_pipeline_data(**kwargs)

    conviction = {
        ticker: combine_horizon_signals(horizons)
        for ticker, horizons in signals.items()
    }

    weights = construct_portfolio(
        signals,
        volatilities,
        max_position=request.max_position,
        gross_exposure=request.gross_exposure,
        portfolio_volatility=port_vol,
        target_volatility=target_vol,
    )

    return RunResponse(
        tickers=list(signals.keys()),
        horizons=list(HORIZONS),
        signals=signals,
        conviction=conviction,
        volatilities=volatilities,
        portfolio_volatility=port_vol,
        target_volatility=target_vol,
        weights=weights,
    )
