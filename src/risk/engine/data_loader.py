# src/data_loader.py
'''
The ingestion engine safely downloads live, high-frequency 
stock data from Yahoo Finance and formats it for the risk pipeline
(Used yf temporarily for testing since it is free to use, can be expanded to other APIs if required)
'''
import yfinance as yf
import pandas as pd

def fetch_market_data(tickers: list, provider: str = "yfinance") -> pd.DataFrame:
    """
    Unified ingestion engine. Ensures that no matter what data vendor 
    is active, the pipeline always receives a standardized DataFrame.
    """
    if provider == "yfinance":
        data = yf.download(tickers, period="5d", interval="1m")
        return data['Close']
     
    elif provider == "alpha_vantage":
        raise NotImplementedError("Alpha Vantage wrapper coming soon.")
        
    else:
        raise ValueError(f"Unknown data provider profile: {provider}")
