import sys
import os
import unittest
import pandas as pd
import numpy as np
from scipy.stats import norm

# The Path Hack
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.config import HORIZONS, RISK, MINUTES_PER_TRADING_DAY
from src.risk.volatility import (
    stock_volatility,
    stock_var,
    portfolio_volatility,
    portfolio_var,
    FORECAST_MINUTES
)
from src.risk.engine.baseline_metrics import calculate_log_returns, calculate_historical_var

class TestVolatilityInterface(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Arrange: Generates a highly correlated, multivariate returns dataset."""
        np.random.seed(42) 
        dates = pd.date_range("2026-07-01", periods=10000, freq="min")
        
        # 1. Define individual target volatilities
        cls.target_vols = {"AAPL": 0.01, "MSFT": 0.015, "NVDA": 0.02}
        vol_array = np.array([cls.target_vols["AAPL"], cls.target_vols["MSFT"], cls.target_vols["NVDA"]])
        
        # 2. Define a realistic correlation matrix for Tech stocks (highly correlated)
        correlation_matrix = np.array([
            [1.0, 0.7, 0.6],  # AAPL
            [0.7, 1.0, 0.8],  # MSFT
            [0.6, 0.8, 1.0]   # NVDA
        ])
        
        # 3. Convert correlation to covariance: diag(vols) * corr * diag(vols)
        target_cov_matrix = np.outer(vol_array, vol_array) * correlation_matrix
        
        # 4. Generate correlated multivariate returns
        means = [0, 0, 0]
        multivariate_returns = np.random.multivariate_normal(means, target_cov_matrix, 10000)
        
        # --- THE UPGRADE: INJECT FLASH CRASHES (FAT TAILS) ---
        # Overwrite two recent rows to simulate a violent market crash.
        # This creates massive negative skew and high kurtosis!
        multivariate_returns[-10] = [-0.15, -0.12, -0.18] 
        multivariate_returns[-5] = [-0.10, -0.08, -0.12]

        cls.returns_df = pd.DataFrame(
            multivariate_returns, 
            columns=["AAPL", "MSFT", "NVDA"], 
            index=dates
        )

        # Portfolio weights
        cls.weights = {"AAPL": 0.4, "MSFT": 0.4, "NVDA": 0.2}

    def test_unknown_horizon_rejected(self):
        """Test the Bouncer: Invalid horizons crash with a ValueError."""
        with self.assertRaises(ValueError):
            stock_var("AAPL", "99d", self.returns_df["AAPL"])

    def test_stock_volatility_math_accuracy(self):
        """Verify baseline volatility calculates the correct scaled standard deviation."""
        print(f"\n--- [STOCK VOLATILITY MATH CHECK (ALL HORIZONS)] ---")
        
        estimation_window = RISK.get("estimation_days", 21) * MINUTES_PER_TRADING_DAY
        lookback_size = min(estimation_window, len(self.returns_df["AAPL"]))
        
        for horizon in HORIZONS:
            with self.subTest(horizon=horizon):
                # Run the function
                vol_result = stock_volatility("AAPL", horizon, self.returns_df["AAPL"])
                
                # Calculate what the exact mathematical answer should be
                windowed_returns = self.returns_df["AAPL"].tail(lookback_size)
                expected_baseline_vol = windowed_returns.std()
                
                forecast_minutes = FORECAST_MINUTES[horizon]
                time_scaler = np.sqrt(forecast_minutes)
                expected_vol = expected_baseline_vol * time_scaler
                
                print(f"[{horizon:>3}] Scaler: {time_scaler:>6.2f}x | Expected: {expected_vol:.5f} | Calc: {vol_result:.5f}")
                
                # check output
                self.assertIsInstance(vol_result, float)
                self.assertAlmostEqual(vol_result, expected_vol, places=5)

    def test_log_returns_math(self):
        """Verify the log returns transformation is mathematically exact."""
        print(f"\n--- [LOG RETURNS MATH CHECK] ---")
        
        # Create dummy prices: 100 -> 105 -> 102
        prices = pd.Series([100.0, 105.0, 102.0])
        
        # The exact expected math: ln(P_t / P_{t-1})
        expected_returns = pd.Series([
            np.log(105.0 / 100.0), 
            np.log(102.0 / 105.0)
        ], index=[1, 2]) 
        
        calc_returns = calculate_log_returns(prices)
        
        pd.testing.assert_series_equal(calc_returns, expected_returns, check_names=False)
        print("Status: Log Returns math is perfectly time-additive!")

    def test_historical_var_math(self):
        """Verify the non-parametric historical VaR correctly finds the worst-case cutoff."""
        print(f"\n--- [HISTORICAL VAR MATH CHECK] ---")
        
        # Generate 1,000 days of normal market returns
        np.random.seed(42)
        mock_returns = pd.Series(np.random.normal(0, 0.02, 1000))
        
        # Inject an artificial "flash crash" (-50%) 
        mock_returns.iloc[0] = -0.50 
        
        # Calculate the 5th percentile 
        expected_var = abs(np.percentile(mock_returns, 5))
        
        calc_var = calculate_historical_var(mock_returns, confidence=0.95)
        
        print(f"Expected VaR Threshold: {expected_var:.5f} | Calculated: {calc_var:.5f}")
        
        self.assertIsInstance(calc_var, float)
        self.assertAlmostEqual(calc_var, expected_var, places=5)

    def test_stock_var_all_horizons(self):
        """Verify the Cornish-Fisher engine dynamically time-scales across ALL horizons."""
        print(f"\n--- [STOCK VAR CHECK (ALL HORIZONS)] ---")
        expected_z = norm.ppf(0.95) 
        estimation_window = RISK.get("estimation_days", 21) * MINUTES_PER_TRADING_DAY
        
        for horizon in HORIZONS:
            with self.subTest(horizon=horizon):
                var_result = stock_var("AAPL", horizon, self.returns_df["AAPL"])
                
                # 1. Expected Lookback
                lookback_size = min(estimation_window, len(self.returns_df["AAPL"]))
                
                # 2. Expected Forecast
                forecast_minutes = FORECAST_MINUTES[horizon]
                time_scaler = np.sqrt(forecast_minutes)
                
                # FIX: Dynamically calculate the expected volatility for this specific slice
                # (This captures the massive standard deviation spike from the flash crash)
                windowed_returns = self.returns_df["AAPL"].tail(lookback_size)
                
                ewma_lambda = RISK["ewma_lambda"]
                slice_vol = windowed_returns.ewm(alpha=1-ewma_lambda).std().iloc[-1]
                
                expected_var = expected_z * slice_vol * time_scaler 
                
                print(f"[{horizon:>3}] Scaler: {time_scaler:>6.2f}x | Expected: {expected_var:.5f} | Calc: {var_result:.5f}")
                
                self.assertIsInstance(var_result, float)
                
                # 35% delta here because the flash crash creates extreme kurtosis,
                # meaning Cornish-Fisher will intentionally (and correctly!) diverge heavily from Standard Normal.
                self.assertAlmostEqual(var_result, expected_var, delta=expected_var * 0.35)

    def test_portfolio_volatility_value_check(self):
        """Verify the covariance matrix resolves to the correct portfolio volatility."""
        port_vol_result = portfolio_volatility(self.weights, "1d", self.returns_df)
        
        estimation_window = RISK.get("estimation_days", 21) * MINUTES_PER_TRADING_DAY
        lookback_size = min(estimation_window, len(self.returns_df))
        
        windowed_returns = self.returns_df.tail(lookback_size)
        w_array = np.array([self.weights["AAPL"], self.weights["MSFT"], self.weights["NVDA"]])
        
        ewma_lambda = RISK["ewma_lambda"]
        expected_cov = windowed_returns.ewm(alpha=1-ewma_lambda).cov().xs(windowed_returns.index[-1], level=0)
        expected_variance = np.dot(w_array.T, np.dot(expected_cov, w_array))

        expected_port_vol = np.sqrt(expected_variance)
        
        self.assertAlmostEqual(port_vol_result, expected_port_vol, places=5)

    def test_portfolio_var_all_horizons(self):
        """Verify the blended super-asset VaR dynamically time-scales across ALL horizons."""
        print(f"\n--- [PORTFOLIO VAR CHECK (ALL HORIZONS)] ---")
        expected_z = norm.ppf(0.95)
        estimation_window = RISK.get("estimation_days", 21) * MINUTES_PER_TRADING_DAY
        
        for horizon in HORIZONS:
            with self.subTest(horizon=horizon):
                port_var_result = portfolio_var(self.weights, horizon, self.returns_df)
                
                # 1. Expected Lookback
                lookback_size = min(estimation_window, len(self.returns_df))
                
                # 2. Expected Forecast
                forecast_minutes = FORECAST_MINUTES[horizon]
                time_scaler = np.sqrt(forecast_minutes)
                
                # FIX: Dynamically calculate the expected volatility for this specific slice
                windowed_returns = self.returns_df.tail(lookback_size)
                w_array = np.array([self.weights["AAPL"], self.weights["MSFT"], self.weights["NVDA"]])
                
                ewma_lambda = RISK["ewma_lambda"]
                port_returns = windowed_returns.dot(w_array)
                slice_port_vol = port_returns.ewm(alpha=1-ewma_lambda).std().iloc[-1]
                
                # Calculate expected VaR using the exact slice volatility
                expected_port_var = expected_z * slice_port_vol * time_scaler
                
                print(f"[{horizon:>3}] Scaler: {time_scaler:>6.2f}x | Expected: {expected_port_var:.5f} | Calc: {port_var_result:.5f}")
                
                self.assertIsInstance(port_var_result, float)
                self.assertAlmostEqual(port_var_result, expected_port_var, delta=expected_port_var * 0.15)
                
if __name__ == '__main__':
    unittest.main(verbosity=2)