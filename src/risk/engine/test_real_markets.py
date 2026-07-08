import sys
import os
import logging
import pandas as pd
import numpy as np

# 1. The Path Hack: Tells Python to look 3 folders UP to find the root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# 2. Clean, direct imports from the master src folder
from src.config import TRADING, RISK
from src.risk.engine.data_loader import fetch_market_data
from src.risk.engine.advanced_risk import calculate_rolling_covariance, calculate_cornish_fisher_multiplier

# 3. Setup Production Logging
logging.basicConfig(
    filename='risk_engine.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.getLogger().addHandler(logging.StreamHandler())

def run_live_market_test():
    logging.info("Initializing live market risk analysis pipeline...")

    # 4. Extract variables directly from the master Python dictionaries
    tickers = TRADING['tickers']
    window_size = RISK['window_size']
    confidence = RISK['confidence']

    # 5. Fetch Data
    logging.info(f"Fetching live data for {tickers} from yfinance...")
    price_data = fetch_market_data(tickers, provider="yfinance")
    
    if price_data.empty:
        logging.warning("Data fetch returned empty. Check API limits.")
        return

    # Calculate log returns
    log_returns = np.log(price_data / price_data.shift(1))

    # 6. OVERNIGHT GAP FIX
    dates = pd.Series(log_returns.index.date, index=log_returns.index)
    is_new_day = dates != dates.shift(1)
    log_returns[is_new_day] = 0.0
    log_returns = log_returns.dropna()

    logging.info(f"Running calculations using a rolling window of {window_size} bars...")

    # 7. Execute Math Engines
    cov_panel = calculate_rolling_covariance(log_returns, window_size=window_size)
    cf_multipliers = calculate_cornish_fisher_multiplier(log_returns, window_size=window_size, confidence=confidence)

    # Output Results
    logging.info("Pipeline execution complete. Displaying quantitative metrics:")
    print("\n--- Rolling Covariance Matrix (Latest Window) ---")
    print(cov_panel.tail(len(tickers)))
    print("\n--- Tail-Adjusted Risk Boundaries ---")
    print(cf_multipliers.tail(5))

if __name__ == "__main__":
    run_live_market_test()