import os
import sys
import time
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.risk.engine.baseline_metrics import calculate_historical_var
from src.risk.engine.data_loader import fetch_market_data

load_dotenv() 
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def generate_agent_signal(ticker, price_history_str, var_confidence, var_value, max_retries=3):
    
    # constructs the prompt and queries Gemini for a trading decision
    # includes a retry loop for temporary API failures
    
    prompt = f"""
    You are a quantitative portfolio manager evaluating a systematic strategy.
    
    Asset: {ticker}
    Recent Price History: {price_history_str}
    Risk Parameter (Value at Risk - {var_confidence}% Confidence): {var_value:.4f}
    
    Based on this data, should we Buy, Sell, or stay Flat? 
    You must output ONLY one of the following words: BUY, SELL, or FLAT.
    """

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,  # temperature is set to 0 for deterministic and repeatable outputs
                )
            )
            return response.text.strip().upper()
            
        except Exception as e:
            error_msg = str(e)
            print(f"API Error for {ticker} (Attempt {attempt + 1}/{max_retries}): {error_msg}")
            
            if attempt < max_retries - 1:
                # if we hit a rate limit (429), force a 60-second cooldown
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    sleep_time = 60
                    print(f"Rate limit hit! Cooling down for {sleep_time} seconds...")
                else:
                    # for standard 503 errors, use fast backoff
                    sleep_time = 2 ** attempt 
                    print(f"Waiting {sleep_time} seconds before retrying...")
                
                time.sleep(sleep_time)
            else:
                print(f"Max retries reached for {ticker}. Defaulting to FLAT.")
                return "FLAT"

def run_parameter_sweep(market_data_df):
    
    # loops through the data and tests different VaR thresholds.
    
    confidence_levels = [0.90, 0.95, 0.99]
    results = {0.90: [], 0.95: [], 0.99: []}
    
    print("--- Starting Agentic LLM Parameter Sweep ---")
    
    for ticker, prices in market_data_df.items():
        price_history_str = str(prices.tolist())
        
        for conf in confidence_levels:
            var_value = calculate_historical_var(prices, confidence=conf) 
            signal = generate_agent_signal(ticker, price_history_str, conf * 100, var_value)
            
            print(f"[{ticker}] {conf*100}% VaR: {var_value:.4f} -> LLM Signal: {signal}")
            results[conf].append({'ticker': ticker, 'signal': signal})
            
            time.sleep(5) # sleep to avoid API rate limits
            
    return results

if __name__ == "__main__":
    print("Loading live data using the data pipeline...")
    
    live_data = fetch_market_data(['AAPL', 'MSFT', 'NVDA'])
    sweep_results = run_parameter_sweep(live_data)
    
    print("\nSweep Complete! Results captured.")
    
    # evaluation check to see how the model leaned across confidence levels
    print("\n--- Strategy Evaluation Summary ---")
    for conf, decisions in sweep_results.items():
        buy_count = sum(1 for d in decisions if d['signal'] == 'BUY')
        total_signals = len(decisions)
        print(f"{conf*100}% VaR track generated {buy_count} BUY signals out of {total_signals} total decisions.")