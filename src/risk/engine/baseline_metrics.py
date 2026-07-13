import pandas as pd
import numpy as np

def calculate_log_returns(prices: pd.Series) -> pd.Series:
    """
    Converts raw historical price data into time-additive log returns.
    """
    return np.log(prices / prices.shift(1)).dropna()

def calculate_baseline_volatility(returns: pd.Series) -> float:
    """
    Computes baseline standard deviation for an individual stock.
    This serves as the foundational 'Wiggle Score'.
    """
    return returns.std()

def calculate_historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Non-parametric Historical Simulation VaR.
    Sorts historical returns to find the empirical worst-case loss threshold.
    """
    percentile = (1 - confidence) * 100
    # np.percentile automatically sorts and finds the exact cutoff
    return abs(np.percentile(returns, percentile))