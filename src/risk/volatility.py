"""Risk and volatility signals — owned by Anish and team.

Two levels, both indexed by the same horizons as the trading strategies:
  1. Single-stock volatility: how much one ticker's returns spread out.
  2. Portfolio-level risk: how much a weighted basket of tickers moves,
     which is not just the average of individual volatilities since stocks
     can move together (correlated) or offset each other.
"""

import pandas as pd
import numpy as np

# Import horizons, risk settings, and the new time constants
from src.config import HORIZONS, RISK, HORIZON_TRADING_DAYS, MINUTES_PER_TRADING_DAY
from src.risk.engine.advanced_risk import calculate_cornish_fisher_multiplier

# Dynamically calculate the historical lookback size from the config
ESTIMATION_WINDOW = RISK["estimation_days"] * MINUTES_PER_TRADING_DAY
EWMA_LAMBDA = RISK["ewma_lambda"]

# Maps string horizons to exact minute counts for forward-scaling
FORECAST_MINUTES = {
    horizon: days * MINUTES_PER_TRADING_DAY 
    for horizon, days in HORIZON_TRADING_DAYS.items()
}

def _validate_stock_inputs(ticker: str, returns: pd.Series):
    """Guards against empty data and NaNs for single-stock calculations."""
    if returns.empty:
        raise ValueError(f"Returns data for {ticker} is empty.")
    if returns.isna().any():
        raise ValueError(f"Returns data for {ticker} contains NaNs. Clean data upstream.")

def _validate_portfolio_inputs(weights: dict[str, float], returns: pd.DataFrame):
    """Guards against bad weights, missing columns, empty data, and NaNs."""
    if returns.empty:
        raise ValueError("Returns DataFrame is empty.")
        
    tickers = list(weights.keys())
    missing = set(tickers) - set(returns.columns)
    if missing:
        raise ValueError(f"Missing returns columns for tickers: {missing}")
        
    if returns[tickers].isna().values.any():
        raise ValueError("Returns data contains NaNs. Clean data upstream before passing to risk engine.")
        
    weight_sum = sum(weights.values())
    if not np.isclose(weight_sum, 1.0):
        raise ValueError(f"Portfolio weights must sum to 1.0. Current sum: {weight_sum}")
    if any(w < 0 for w in weights.values()):
        raise ValueError("Negative weights detected. Risk engine currently assumes long-only portfolios.")

def stock_volatility(ticker: str, horizon: str, returns: pd.Series) -> float:
    """TODO(Ayush): standard deviation of `ticker` returns over `horizon`."""
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {horizon}")
    
    raise NotImplementedError("stock_volatility not yet implemented by Ayush")

def stock_var(ticker: str, horizon: str, returns: pd.Series, confidence: float = 0.95) -> float:
    """Value-at-Risk for `ticker` over `horizon` using Cornish-Fisher expansion."""
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {horizon}")
    
    _validate_stock_inputs(ticker, returns)
    
    # 1. THE LOOKBACK: Slice a stable, statistically significant chunk of history
    lookback_size = min(ESTIMATION_WINDOW, len(returns))
    windowed_returns = returns.tail(lookback_size) # Slice the fixed historical estimation window.
    returns_df = windowed_returns.to_frame(name=ticker)
    
    cf_z_scores = calculate_cornish_fisher_multiplier(returns_df, window_size=lookback_size, confidence=confidence)
    latest_z = cf_z_scores.iloc[-1][ticker]
    
    #UPGRADE: Exponentially Weighted Standard Deviation
    volatility = windowed_returns.ewm(alpha=1-EWMA_LAMBDA).std().iloc[-1] # Calculate standard deviation ONLY on the sliced window
    
    # 2. THE FORECAST: Scale the risk forward based on the requested horizon
    forecast_minutes = FORECAST_MINUTES[horizon]  # Direct access, no fallback
    time_scaler = np.sqrt(forecast_minutes)
    
    return float(abs(latest_z * volatility * time_scaler))

def portfolio_volatility(weights: dict[str, float], horizon: str, returns: pd.DataFrame) -> float:
    """Portfolio-level volatility for `weights` over `horizon`,
    accounting for covariance between tickers (not just weighted-average of
    single-stock volatilities).
    
    Note: Estimated from the fixed estimation window and is horizon-independent. 
    `horizon` is required for interface consistency with the broader pipeline.
    """
    
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {horizon}")
    
    _validate_portfolio_inputs(weights, returns)

    tickers = list(weights.keys())
    w_array = np.array([weights[t] for t in tickers])
    
    # Filters and aligns the returns DataFrame to match the exact order of the weights array
    aligned_returns = returns[tickers]
    
    # Slice using the stable estimation window
    lookback_size = min(ESTIMATION_WINDOW, len(aligned_returns))
    windowed_returns = aligned_returns.tail(lookback_size)

    # UPGRADE: Generate EWMA covariance matrix and extract the final timestamp's matrix
    ewm_cov = windowed_returns.ewm(alpha=1-EWMA_LAMBDA).cov()
    cov_matrix = ewm_cov.xs(windowed_returns.index[-1], level=0)
    
    # Execute standard portfolio variance linear algebra: w^T * Sigma * w
    port_variance = np.dot(w_array.T, np.dot(cov_matrix, w_array))

    return float(np.sqrt(port_variance))

def portfolio_var(weights: dict[str, float], horizon: str, returns: pd.DataFrame, confidence: float = 0.95) -> float:
    """Portfolio-level Value-at-Risk for `weights` over `horizon`."""
    if horizon not in HORIZONS:
        raise ValueError(f"Unknown horizon: {horizon}")
    
    _validate_portfolio_inputs(weights, returns)
    
    tickers = list(weights.keys())
    w_array = np.array([weights[t] for t in tickers])
    aligned_returns = returns[tickers]
    
    # This multiplies every single minute's return by 
    # portfolio weights and adds them together.
    
    
    # 1. THE LOOKBACK: Slice a stable, statistically significant chunk of history
    lookback_size = min(ESTIMATION_WINDOW, len(aligned_returns))
    windowed_returns = aligned_returns.tail(lookback_size)

    # Calculate 1D portfolio returns

    port_returns = windowed_returns.dot(w_array)
    # Convert to DataFrame and get the rolling Z-score for the whole basket
    port_returns_df = port_returns.to_frame(name='Portfolio')
    
    cf_z_scores = calculate_cornish_fisher_multiplier(port_returns_df, window_size=lookback_size, confidence=confidence)

    # Grabs the final, most up-to-date dynamic Z-score ($Z_{CF}$) for the current minute.
    latest_z = cf_z_scores.iloc[-1]['Portfolio']
    
    # Calculate standard deviation directly from the 1D returns array using EWMA
    port_vol = port_returns.ewm(alpha=1-EWMA_LAMBDA).std().iloc[-1]     # O(T) Optimization: Standard deviation of 1D linear returns matches covariance matrix output

    # Apply Square Root of Time Scaling
    # 2. THE FORECAST: Scale the risk forward based on the requested horizon
    forecast_minutes = FORECAST_MINUTES[horizon]

    time_scaler = np.sqrt(forecast_minutes)

    
    # VaR = Tail-adjusted Z-score * Portfolio Volatility * Sqrt(Time)
    return float(abs(latest_z * port_vol * time_scaler))