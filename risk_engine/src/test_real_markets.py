import json
import logging
import pandas as pd
import numpy as np
from data_loader import fetch_market_data
from advanced_risk import calculate_rolling_covariance, calculate_cornish_fisher_multiplier

# 1. Setup Production Logging
logging.basicConfig(
    filename='risk_engine.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Also print to the terminal to watch it live
logging.getLogger().addHandler(logging.StreamHandler())

def run_live_market_test():
    logging.info("Initializing live market risk analysis pipeline...")

    # 2. Load External Configuration
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        logging.info("Configuration loaded successfully.")
    except FileNotFoundError:
        logging.error("config.json not found. Pipeline aborted.")
        return

    # Extract variables
    tickers = config['trading']['tickers']
    window_size = config['risk']['window_size']
    confidence = config['risk']['confidence']

    # 3. Fetch Data
    logging.info(f"Fetching live data for {tickers} from yfinance...")
    price_data = fetch_market_data(tickers, provider="yfinance")
    
    if price_data.empty:
        logging.warning("Data fetch returned empty. Check API limits.")
        return

    # Calculate log returns
    log_returns = np.log(price_data / price_data.shift(1))

    # 4. OVERNIGHT GAP FIX: Zero out returns at the market open
    # We compare the date of the current minute to the date of the previous minute
    dates = pd.Series(log_returns.index.date, index=log_returns.index)
    is_new_day = dates != dates.shift(1)
    
    # Force the first minute of every new day to 0.0 to prevent artificial volatility spikes
    log_returns[is_new_day] = 0.0
    
    # Drop the first NaN row created by the shift
    log_returns = log_returns.dropna()

    logging.info(f"Running calculations using a rolling window of {window_size} bars...")

    # 5. Execute Math Engines
    cov_panel = calculate_rolling_covariance(log_returns, window_size=window_size)
    cf_multipliers = calculate_cornish_fisher_multiplier(log_returns, window_size=window_size, confidence=confidence)

    # Output Results
    logging.info("Pipeline execution complete. Displaying quantitative metrics:")
    
    print("\n--- Rolling Covariance Matrix (Latest Window) ---")
    # Grabs the exact number of rows needed to show the final full matrix for your tickers
    print(cov_panel.tail(len(tickers)))

    print("\n--- Tail-Adjusted Risk Boundaries ---")
    print(cf_multipliers.tail(5))

if __name__ == "__main__":
    run_live_market_test()