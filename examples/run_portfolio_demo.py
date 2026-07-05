"""Demo: proves the portfolio construction pipeline end-to-end using made-up
signal and volatility numbers, standing in for Jin's and Anish's modules
until those are implemented (src/signals/strategies.py, src/risk/volatility.py).

Run: python -m examples.run_portfolio_demo
"""

from examples.fake_data import load_fake_data
from src.portfolio.construction import combine_horizon_signals, construct_portfolio

if __name__ == "__main__":
    signals_by_ticker_horizon, volatilities_by_ticker, portfolio_volatility, target_volatility = load_fake_data()

    print("Combined conviction score per ticker (AAPL's horizons disagree, so it gets damped):")
    for ticker, horizons in signals_by_ticker_horizon.items():
        print(f"  {ticker:6s} {combine_horizon_signals(horizons):+.3f}")

    weights = construct_portfolio(
        signals_by_ticker_horizon,
        volatilities_by_ticker,
        max_position=0.15,
        gross_exposure=1.0,
        portfolio_volatility=portfolio_volatility,
        target_volatility=target_volatility,
    )

    print("\nFinal portfolio weights:")
    for ticker, weight in weights.items():
        print(f"  {ticker:6s} {weight:+.3f}")
