# agentic-trading

Quant research platform: trading signals + risk/volatility signals -> portfolio construction, across horizons 1d/3d/5d/10d/15d/1m/3m (`src/config.py`).

- `src/signals/strategies.py` (Jin) — one function per horizon, returns a score in [-1, 1]. Currently stubbed, raises `NotImplementedError`.
- `src/risk/volatility.py` (Anish) — single-stock and portfolio-level volatility/VaR per horizon. Currently stubbed, raises `NotImplementedError`.
- `src/portfolio/construction.py` (Yashwanth) — combines the two into position weights: blends per-horizon signals per ticker (damping conflicting horizons instead of picking a side), sizes positions inversely to volatility, caps per-name exposure, and scales the book to a target portfolio risk. Implemented.

Run `python -m examples.run_portfolio_demo` to see the construction pipeline working end-to-end on made-up signal/volatility numbers, standing in for the real modules until those land.
