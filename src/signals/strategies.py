"""Trading signal strategies — owned by Jin.

Each horizon gets its own function. A strategy takes a price history for one
ticker and returns a score in [-1, 1]: -1 = sell, 0 = flat, +1 = buy. Scores
don't have to be exactly -1/0/+1 — continuous strength (e.g. 0.4) is fine and
lets the portfolio layer weigh conviction, not just direction.

Strategy-to-horizon mapping:
  1d  → VWAP Breakout Momentum
  3d  → ConnorsRSI Mean Reversion
  5d  → Bollinger Band Volatility Squeeze
  10d → SMA(10)/SMA(50) Momentum + RSI(14)
  15d → Fama-French Residual Reversal (price-only proxy)
  1m  → Low-Turnover Short-Term Reversal (price-only proxy)
  3m  → Jegadeesh-Titman Momentum (skip last month)
"""

import numpy as np
import pandas as pd

from src.config import HORIZONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rsi(prices: pd.Series, period: int) -> pd.Series:
    """Wilder RSI using exponential smoothing."""
    delta = prices.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))


def _streak(returns: pd.Series) -> pd.Series:
    """Signed consecutive-run counter: +N for N up days, -N for N down days."""
    counts = []
    n = 0
    for r in returns:
        if np.isnan(r):
            counts.append(0.0)
            continue
        if r > 0:
            n = n + 1 if n > 0 else 1
        elif r < 0:
            n = n - 1 if n < 0 else -1
        else:
            n = 0
        counts.append(float(n))
    return pd.Series(counts, index=returns.index, dtype=float)


def _percent_rank(series: pd.Series, window: int) -> pd.Series:
    """Percent rank of each value vs the previous `window - 1` values (0–100)."""
    return series.rolling(window).apply(
        lambda x: float((x[:-1] < x[-1]).sum()) / (len(x) - 1) * 100,
        raw=True,
    )


def _zscore_last(series: pd.Series, window: int) -> float:
    """Z-score of the most recent value relative to the last `window` obs."""
    recent = series.iloc[-window:]
    mu, sigma = recent.mean(), recent.std()
    return float((series.iloc[-1] - mu) / (sigma + 1e-9))


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

def signal_1d(prices: pd.Series) -> float:
    """VWAP Breakout Momentum.

    Approximates VWAP with a 20-bar rolling mean. Prices closing above VWAP
    with a confirming RSI(3) score positively; below with an opposing RSI score
    negatively. Signal strength is proportional to the z-scored deviation.
    """
    if len(prices) < 20:
        return 0.0
    rolling = prices.rolling(20)
    vwap = rolling.mean().iloc[-1]
    std = rolling.std().iloc[-1]
    rsi3 = _rsi(prices, 3).iloc[-1]

    deviation = (prices.iloc[-1] - vwap) / (2 * std + 1e-9)
    signal = float(np.tanh(deviation * 2))

    if signal > 0 and rsi3 < 55:
        signal *= 0.5
    elif signal < 0 and rsi3 > 45:
        signal *= 0.5

    return float(np.clip(signal, -1.0, 1.0))


def signal_3d(prices: pd.Series) -> float:
    """ConnorsRSI Mean Reversion.

    CRSI = (RSI(3) + RSI_streak(2) + PercentRank(100)) / 3
    CRSI near 0 (deeply oversold) scores +1; near 100 (deeply overbought) scores -1.
    Requires at least 102 bars so all three sub-components are meaningful.
    """
    if len(prices) < 102:
        return 0.0
    returns = prices.pct_change()
    rsi3 = _rsi(prices, 3)
    rsi_streak = _rsi(_streak(returns), 2)
    prank = _percent_rank(returns, 100)
    crsi = ((rsi3 + rsi_streak + prank) / 3).iloc[-1]
    return float(np.clip((50.0 - crsi) / 50.0, -1.0, 1.0))


def signal_5d(prices: pd.Series) -> float:
    """Bollinger Band Volatility Squeeze.

    Measures band-width compression relative to the 126-bar (≈6-month) minimum.
    When width is near its tightest, price breaking above/below the band triggers
    a directional signal proportional to squeeze intensity.
    """
    if len(prices) < 130:
        return 0.0
    window = 20
    mid = prices.rolling(window).mean()
    std = prices.rolling(window).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    width = (upper - lower) / (mid + 1e-9)

    min_width_6m = width.rolling(126).min().iloc[-1]
    squeeze = float(np.clip(1.0 - (width.iloc[-1] - min_width_6m) / (min_width_6m + 1e-9), 0.0, 1.0))
    direction = float(np.sign(prices.iloc[-1] - mid.iloc[-1]))

    return float(np.clip(squeeze * direction, -1.0, 1.0))


def signal_10d(prices: pd.Series) -> float:
    """SMA(10)/SMA(50) Momentum + RSI(14).

    Bullish when the fast MA is above the slow MA and RSI confirms above 50.
    Signal strength combines the relative MA spread (via tanh) with the RSI
    deviation from neutral, weighted 60/40.
    """
    if len(prices) < 50:
        return 0.0
    sma10 = prices.rolling(10).mean().iloc[-1]
    sma50 = prices.rolling(50).mean().iloc[-1]
    rsi14 = _rsi(prices, 14).iloc[-1]

    ma_signal = float(np.tanh((sma10 - sma50) / (sma50 * 0.02 + 1e-9)))
    rsi_signal = (rsi14 - 50.0) / 50.0

    return float(np.clip(0.6 * ma_signal + 0.4 * rsi_signal, -1.0, 1.0))


def signal_15d(prices: pd.Series) -> float:
    """Fama-French Residual Reversal (price-only proxy).

    Z-scores the 15-day return over the trailing year and fades it: recent
    outperformers are expected to revert, underperformers to recover.
    Uses 252 bars so the z-score is statistically meaningful.
    """
    if len(prices) < 252:
        return 0.0
    ret15 = prices.pct_change(15).dropna()
    z = _zscore_last(ret15, 252)
    return float(np.clip(-z / 2.0, -1.0, 1.0))


def signal_1m(prices: pd.Series) -> float:
    """Low-Turnover Short-Term Reversal (price-only proxy).

    Fades the 21-day (≈1-month) return: extreme losers tend to bounce,
    extreme recent winners tend to pull back. Strength scales with z-score.
    """
    if len(prices) < 252:
        return 0.0
    ret21 = prices.pct_change(21).dropna()
    z = _zscore_last(ret21, 252)
    return float(np.clip(-z / 2.0, -1.0, 1.0))


def signal_3m(prices: pd.Series) -> float:
    """Jegadeesh-Titman Momentum (3-month formation, skip last month).

    Computes the 63-trading-day return ending 21 days ago (skipping the
    short-term reversal window), then z-scores it over trailing history.
    High past return → positive score; low past return → negative score.
    """
    if len(prices) < 85:
        return 0.0
    ret_jt = (prices.iloc[-22] - prices.iloc[-85]) / (prices.iloc[-85] + 1e-9)
    ret_series = prices.pct_change(63).dropna()
    mu, sigma = ret_series.mean(), ret_series.std()
    z = (ret_jt - mu) / (sigma + 1e-9)
    return float(np.clip(z / 2.0, -1.0, 1.0))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

STRATEGIES = {
    "1d": signal_1d,
    "3d": signal_3d,
    "5d": signal_5d,
    "10d": signal_10d,
    "15d": signal_15d,
    "1m": signal_1m,
    "3m": signal_3m,
}


def get_signal(ticker: str, horizon: str, prices: pd.Series) -> float:
    """Score in [-1, 1] for `ticker` at `horizon`, using its price history."""
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {horizon}")
    return STRATEGIES[horizon](prices)


# Structured catalog (core rule + description) for reports, agent seeds, and docs.
# Kept machine-readable so discovery / desks can cite principle text without scraping markdown.
HORIZON_CATALOG: dict[str, dict[str, str]] = {
    "1d": {
        "name": "VWAP Breakout Momentum",
        "rule": (
            "Compare last price to a 20-bar rolling average, scale by 20-bar volatility, "
            "then soften if RSI(3) does not confirm."
        ),
        "description": (
            "Short-term momentum that buys when price breaks above its recent average and "
            "sells when it falls below, with signal strength reduced if very short-term momentum is weak."
        ),
    },
    "3d": {
        "name": "ConnorsRSI Mean Reversion",
        "rule": (
            "Average RSI(3), RSI of the up/down streak, and 100-bar return percent rank; "
            "low values become buy, high values become sell."
        ),
        "description": (
            "Mean-reversion for a 3-day horizon; looks for oversold conditions to buy and "
            "overbought conditions to sell using a blended short-term momentum score."
        ),
    },
    "5d": {
        "name": "Bollinger Band Volatility Squeeze",
        "rule": (
            "Measure 20-bar Bollinger band width relative to its 126-bar minimum, then "
            "multiply squeeze intensity by whether price is above or below the mid-band."
        ),
        "description": (
            "When volatility is unusually low, treats a move away from the middle band as a "
            "stronger directional breakout signal."
        ),
    },
    "10d": {
        "name": "SMA(10)/SMA(50) Momentum + RSI(14)",
        "rule": (
            "Combine the normalized gap between 10-day and 50-day moving averages (60%) "
            "with RSI(14) centered at 50 (40%)."
        ),
        "description": (
            "Medium-short momentum that favors a bullish stance when the fast average is above "
            "the slow average and RSI is supportive."
        ),
    },
    "15d": {
        "name": "Fama-French Residual Reversal proxy",
        "rule": (
            "Z-score the most recent 15-day return versus the past 252 such returns, "
            "invert the sign, and scale by 0.5."
        ),
        "description": (
            "A 15-day reversal signal that sells after unusually strong recent returns and "
            "buys after unusually weak recent returns."
        ),
    },
    "1m": {
        "name": "Low-Turnover Short-Term Reversal",
        "rule": (
            "Z-score the 21-day return against the prior year of 21-day returns, invert and scale by 0.5."
        ),
        "description": (
            "A one-month reversal signal that expects strong recent performance to pull back and "
            "weak recent performance to recover."
        ),
    },
    "3m": {
        "name": "Jegadeesh-Titman Momentum (skip last month)",
        "rule": (
            "Take the 63-day return ending 21 days ago, compare it to the history of 63-day "
            "returns as a z-score, then scale by 0.5."
        ),
        "description": (
            "Medium-term momentum that rewards strong prior 3-month performance while avoiding "
            "the most recent month's short-term reversal effects."
        ),
    },
}


def horizon_principle(horizon: str) -> str:
    """One-line principle text for agent reports / catalog seeds."""
    meta = HORIZON_CATALOG.get(horizon) or {}
    name = meta.get("name") or horizon
    desc = meta.get("description") or meta.get("rule") or ""
    return f"{name}: {desc}".strip()
