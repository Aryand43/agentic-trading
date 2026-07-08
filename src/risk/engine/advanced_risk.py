# src/advanced_risk.py
'''
Calculates dynamic risk boundaries (Cornish-Fisher) and tracks how multiple stocks move together in real-time (Covariance) to protect the portfolio from sudden market crashes.
'''
import pandas as pd
import numpy as np
from scipy.stats import norm

def calculate_rolling_covariance(returns_df: pd.DataFrame, window_size: int) -> pd.DataFrame:
    """
    Computes a 3D panel of rolling multi-asset covariance matrices.

    Args:
        returns_df (pd.DataFrame): Time-additive log returns of the asset universe.
        window_size (int): The operational bar count for the horizon (e.g., 390 for 1d).

    Returns:
        pd.DataFrame: A MultiIndexed DataFrame containing the rolling covariance matrices.
    """
    # Ensure window is large enough to avoid linear algebra singularity errors
    effective_window = max(window_size, len(returns_df.columns) + 1)
    
    # Calculate the rolling multi-asset covariance map
    rolling_cov = returns_df.rolling(window=effective_window).cov()
    
    return rolling_cov

def calculate_cornish_fisher_multiplier(returns_df: pd.DataFrame, window_size: int, confidence: float = 0.95) -> pd.DataFrame:
    """
    Adjusts standard risk boundaries using rolling Skewness and Kurtosis.

    Args:
        returns_df (pd.DataFrame): Time-additive log returns.
        window_size (int): The operational bar count for the lookback horizon.
        confidence (float): The desired confidence interval (default 95%).

    Returns:
        pd.DataFrame: A rolling DataFrame of dynamically adjusted Z-scores per asset.
    """
    # 1. Baseline Z-score for standard normal distribution
    z_alpha = norm.ppf(1 - confidence)
    
    # 2. Track rolling moments (Minimum window of 5 required for mathematical kurtosis)
    calc_window = max(window_size, 5)
    rolling_skew = returns_df.rolling(window=calc_window).skew()
    rolling_kurt = returns_df.rolling(window=calc_window).kurt()
    
    # 3. Apply the Cornish-Fisher Expansion Equation
    z_cf = (
        z_alpha + 
        (1/6) * (z_alpha**2 - 1) * rolling_skew + 
        (1/24) * (z_alpha**3 - 3*z_alpha) * rolling_kurt - 
        (1/36) * (2*z_alpha**3 - 5*z_alpha) * (rolling_skew**2)
    )
    
    # 4. Fill initial NaN gaps with the baseline Z-score
    return z_cf.fillna(z_alpha)