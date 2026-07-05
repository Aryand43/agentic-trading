"""Portfolio construction — combines Jin's trading signals with Anish's risk
metrics into position weights.

Three steps, applied in order:
  1. combine_horizon_signals   — for one ticker, blend its 1d..3m signals into
                                  a single conviction score, damping the score
                                  when horizons disagree instead of picking a
                                  side arbitrarily.
  2. risk_adjusted_weights     — across tickers, size each position inversely
                                  to its volatility so riskier names get less
                                  capital for the same signal strength.
  3. apply_portfolio_risk_limit — scale the whole book up or down so total
                                  portfolio risk lands at a target level.
"""

from src.config import HORIZONS


def combine_horizon_signals(
    signals_by_horizon: dict[str, float],
    horizon_weights: dict[str, float] | None = None,
) -> float:
    """Blend one ticker's per-horizon scores into a single conviction score.

    Horizons that disagree in direction cancel each other out via the
    weighted average; `agreement` then damps the result further so a stock
    with split opinions ends up close to flat rather than following whichever
    horizon happens to dominate the average.
    """
    if not signals_by_horizon:
        return 0.0

    unknown = set(signals_by_horizon) - set(HORIZONS)
    if unknown:
        raise ValueError(f"Unknown horizon(s): {unknown}")

    if horizon_weights is None:
        horizon_weights = {h: 1.0 for h in signals_by_horizon}

    total_weight = sum(horizon_weights[h] for h in signals_by_horizon)
    if total_weight == 0:
        return 0.0

    combined = sum(signals_by_horizon[h] * horizon_weights[h] for h in signals_by_horizon) / total_weight

    if combined == 0:
        return 0.0

    agreement = (
        sum(
            horizon_weights[h] * (1.0 if signals_by_horizon[h] * combined >= 0 else 0.0)
            for h in signals_by_horizon
        )
        / total_weight
    )

    return combined * agreement


def risk_adjusted_weights(
    combined_scores: dict[str, float],
    volatilities: dict[str, float],
    max_position: float = 0.1,
    gross_exposure: float = 1.0,
    min_volatility: float = 1e-6,
) -> dict[str, float]:
    """Turn per-ticker conviction scores into position weights, sized down
    for volatile names and capped per-name at `max_position`, then scaled so
    total gross exposure (sum of absolute weights) equals `gross_exposure`.
    """
    missing = set(combined_scores) - set(volatilities)
    if missing:
        raise ValueError(f"Missing volatility for ticker(s): {missing}")

    raw = {
        ticker: score / max(volatilities[ticker], min_volatility)
        for ticker, score in combined_scores.items()
    }
    capped = {ticker: max(-max_position, min(max_position, w)) for ticker, w in raw.items()}

    gross = sum(abs(w) for w in capped.values())
    if gross == 0:
        return {ticker: 0.0 for ticker in capped}

    scale = gross_exposure / gross
    return {ticker: w * scale for ticker, w in capped.items()}


def apply_portfolio_risk_limit(
    weights: dict[str, float],
    portfolio_volatility: float,
    target_volatility: float,
    max_leverage: float = 2.0,
) -> dict[str, float]:
    """Scale the whole portfolio so its realized volatility matches
    `target_volatility`, capped at `max_leverage` to avoid blowing up
    position sizes when measured portfolio risk is near zero.
    """
    if portfolio_volatility <= 0:
        return weights

    scale = min(target_volatility / portfolio_volatility, max_leverage)
    return {ticker: w * scale for ticker, w in weights.items()}


def construct_portfolio(
    signals_by_ticker_horizon: dict[str, dict[str, float]],
    volatilities_by_ticker: dict[str, float],
    horizon_weights: dict[str, float] | None = None,
    max_position: float = 0.1,
    gross_exposure: float = 1.0,
    portfolio_volatility: float | None = None,
    target_volatility: float | None = None,
    max_leverage: float = 2.0,
) -> dict[str, float]:
    """End-to-end: per-horizon signals + per-ticker volatility -> final weights.

    `portfolio_volatility` / `target_volatility` are optional — pass both to
    also scale the book to a target portfolio-level risk (from Anish's
    portfolio_volatility / portfolio_var functions).
    """
    combined_scores = {
        ticker: combine_horizon_signals(horizons, horizon_weights)
        for ticker, horizons in signals_by_ticker_horizon.items()
    }

    weights = risk_adjusted_weights(
        combined_scores, volatilities_by_ticker, max_position, gross_exposure
    )

    if portfolio_volatility is not None and target_volatility is not None:
        weights = apply_portfolio_risk_limit(weights, portfolio_volatility, target_volatility, max_leverage)

    return weights
