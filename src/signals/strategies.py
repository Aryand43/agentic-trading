"""Trading signal strategies — owned by Jin.

Each horizon gets its own function. A strategy takes a price history for one
ticker and returns a score in [-1, 1]: -1 = sell, 0 = flat, +1 = buy. Scores
don't have to be exactly -1/0/+1 — continuous strength (e.g. 0.4) is fine and
lets the portfolio layer weigh conviction, not just direction.

Fill in the formula/rule and description for each horizon below, then update
STRATEGIES so the rest of the pipeline can call them by horizon name.
"""

import pandas as pd

from src.config import HORIZONS


def signal_1d(prices: pd.Series) -> float:
    """TODO(Jin): formula + description for the 1d strategy."""
    raise NotImplementedError("signal_1d not yet implemented")


def signal_3d(prices: pd.Series) -> float:
    """TODO(Jin): formula + description for the 3d strategy."""
    raise NotImplementedError("signal_3d not yet implemented")


def signal_5d(prices: pd.Series) -> float:
    """TODO(Jin): formula + description for the 5d strategy."""
    raise NotImplementedError("signal_5d not yet implemented")


def signal_10d(prices: pd.Series) -> float:
    """TODO(Jin): formula + description for the 10d strategy."""
    raise NotImplementedError("signal_10d not yet implemented")


def signal_15d(prices: pd.Series) -> float:
    """TODO(Jin): formula + description for the 15d strategy."""
    raise NotImplementedError("signal_15d not yet implemented")


def signal_1m(prices: pd.Series) -> float:
    """TODO(Jin): formula + description for the 1m strategy."""
    raise NotImplementedError("signal_1m not yet implemented")


def signal_3m(prices: pd.Series) -> float:
    """TODO(Jin): formula + description for the 3m strategy."""
    raise NotImplementedError("signal_3m not yet implemented")


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
